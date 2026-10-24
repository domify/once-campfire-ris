// The messages page of bench/messages_page.ri in Go, for comparison: the same
// SQLite database, the same signed session cookie, the same markup
// (markup.json, from gen_markup.py) and the same per-message fragment cache.
//
//	go build -o messages_page_go . && GOMAXPROCS=1 ./messages_page_go DB SECRET_KEY_BASE PORT
package main

import (
	"crypto/hmac"
	"crypto/pbkdf2"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

const sqliteTime = "2006-01-02 15:04:05.999999"

type fragment struct {
	version int64
	html    string
}

type app struct {
	db                                           *sql.DB
	cookieKey                                    []byte
	signedIDKey                                  []byte
	parts                                        []string
	mu                                           sync.RWMutex
	cache                                        map[int64]fragment
	session, member, anchor, pageIDs, full, user *sql.Stmt
}

func must[T any](v T, err error) T {
	if err != nil {
		panic(err)
	}
	return v
}

// Rails' signed cookie: base64(JSON envelope)--hex(HMAC-SHA1), the token inside
// as base64(JSON string), for purpose "cookie.session_token".
func (a *app) sessionToken(raw string) (string, bool) {
	raw, err := url.QueryUnescape(raw)
	if err != nil {
		return "", false
	}
	data, digest, ok := strings.Cut(raw, "--")
	if !ok {
		return "", false
	}
	mac := hmac.New(sha1.New, a.cookieKey)
	mac.Write([]byte(data))
	if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(mac.Sum(nil))), []byte(digest)) != 1 {
		return "", false
	}
	var envelope struct {
		Rails struct {
			Message string `json:"message"`
			Pur     string `json:"pur"`
		} `json:"_rails"`
	}
	if json.Unmarshal(must(base64.StdEncoding.DecodeString(data)), &envelope) != nil || envelope.Rails.Pur != "cookie.session_token" {
		return "", false
	}
	var token string
	if json.Unmarshal(must(base64.StdEncoding.DecodeString(envelope.Rails.Message)), &token) != nil {
		return "", false
	}
	return token, true
}

// `user.signed_id(purpose: :avatar)`
func (a *app) avatarToken(userID int64) string {
	data := base64.RawURLEncoding.EncodeToString(fmt.Appendf(nil, `{"_rails":{"data":%d,"pur":"user/avatar"}}`, userID))
	mac := hmac.New(sha256.New, a.signedIDKey)
	mac.Write([]byte(data))
	return data + "--" + hex.EncodeToString(mac.Sum(nil))
}

// ERB::Util.html_escape
var htmlEscaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;", "'", "&#39;")

func escape(s string) string { return htmlEscaper.Replace(s) }

func ms(t time.Time) int64 { return t.UnixMilli() }

func (a *app) fill(roomID int64, anchorCreated string) {
	rows := must(a.full.Query(roomID, anchorCreated))
	defer rows.Close()
	users := map[int64][2]string{}
	for rows.Next() {
		var id, creator int64
		var cid, created, updated, roomName string
		var body sql.NullString
		must(0, rows.Scan(&id, &creator, &cid, &created, &updated, &body, &roomName))
		who, ok := users[creator]
		if !ok {
			var name, userUpdated string
			must(0, a.user.QueryRow(creator).Scan(&name, &userUpdated))
			u := must(time.Parse(sqliteTime, userUpdated))
			who = [2]string{name, fmt.Sprintf("/users/%s/avatar?v=%s", a.avatarToken(creator), u.Format("20060102150405"))}
			users[creator] = who
		}
		c := must(time.Parse(sqliteTime, created))
		u := must(time.Parse(sqliteTime, updated))
		var b strings.Builder
		for i, part := range a.parts {
			if i%2 == 0 {
				b.WriteString(part)
				continue
			}
			switch part {
			case "UPD":
				b.WriteString(strconv.FormatInt(ms(u), 10))
			case "MS":
				b.WriteString(strconv.FormatInt(ms(c), 10))
			case "ISO":
				b.WriteString(c.UTC().Format("2006-01-02T15:04:05Z"))
			case "CID":
				b.WriteString(escape(cid))
			case "MID":
				b.WriteString(strconv.FormatInt(id, 10))
			case "RID":
				b.WriteString(strconv.FormatInt(roomID, 10))
			case "UID":
				b.WriteString(strconv.FormatInt(creator, 10))
			case "AVATAR":
				b.WriteString(escape(who[1]))
			case "NAME":
				b.WriteString(escape(who[0]))
			case "ROOM":
				b.WriteString(escape(roomName))
			case "BODY":
				b.WriteString(body.String)
			}
		}
		a.mu.Lock()
		a.cache[id] = fragment{ms(u), b.String()}
		a.mu.Unlock()
	}
}

func (a *app) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) != 4 || parts[1] != "rooms" || parts[3] != "messages" {
		http.NotFound(w, r)
		return
	}
	roomID, err1 := strconv.ParseInt(parts[2], 10, 64)
	before, err2 := strconv.ParseInt(r.URL.Query().Get("before"), 10, 64)
	if err1 != nil || err2 != nil {
		http.NotFound(w, r)
		return
	}
	cookie, err := r.Cookie("session_token")
	if err != nil {
		w.WriteHeader(401)
		return
	}
	token, ok := a.sessionToken(cookie.Value)
	if !ok {
		w.WriteHeader(401)
		return
	}
	var userID int64
	if a.session.QueryRow(token).Scan(&userID) != nil {
		w.WriteHeader(401)
		return
	}
	var one int
	if a.member.QueryRow(roomID, userID).Scan(&one) != nil {
		http.NotFound(w, r)
		return
	}
	var anchorCreated string
	if a.anchor.QueryRow(roomID, before).Scan(&anchorCreated) != nil {
		http.NotFound(w, r)
		return
	}

	rows := must(a.pageIDs.Query(roomID, anchorCreated))
	ids := make([]int64, 0, 40)
	versions := make([]int64, 0, 40)
	for rows.Next() {
		var id int64
		var updated string
		must(0, rows.Scan(&id, &updated))
		ids = append(ids, id)
		versions = append(versions, ms(must(time.Parse(sqliteTime, updated))))
	}
	rows.Close()

	a.mu.RLock()
	stale := false
	for i, id := range ids {
		if f, ok := a.cache[id]; !ok || f.version != versions[i] {
			stale = true
		}
	}
	a.mu.RUnlock()
	if stale {
		a.fill(roomID, anchorCreated)
	}

	a.mu.RLock()
	total := 0
	for _, id := range ids {
		total += len(a.cache[id].html)
	}
	page := make([]byte, 0, total)
	for i := len(ids) - 1; i >= 0; i-- {
		page = append(page, a.cache[ids[i]].html...)
	}
	a.mu.RUnlock()

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Content-Length", strconv.Itoa(len(page)))
	w.Write(page)
}

func main() {
	db := must(sql.Open("sqlite3", os.Args[1]))
	// Keep a connection per worker: the default keeps 2 idle, and reopening
	// SQLite connections under load costs more than the page.
	db.SetMaxOpenConns(64)
	db.SetMaxIdleConns(64)
	secret := os.Args[2]
	var parts []string
	must(0, json.Unmarshal(must(os.ReadFile("markup.json")), &parts))
	a := &app{
		db:          db,
		cookieKey:   must(pbkdf2.Key(sha256.New, secret, []byte("signed cookie"), 1000, 64)),
		signedIDKey: must(pbkdf2.Key(sha256.New, secret, []byte("active_record/signed_id"), 1000, 64)),
		parts:       parts,
		cache:       map[int64]fragment{},
		session:     must(db.Prepare(`SELECT "user_id" FROM "sessions" WHERE "token" = ? LIMIT 1`)),
		member:      must(db.Prepare(`SELECT 1 FROM "memberships" WHERE "room_id" = ? AND "user_id" = ?`)),
		anchor:      must(db.Prepare(`SELECT "created_at" FROM "messages" WHERE "room_id" = ? AND "id" = ?`)),
		pageIDs:     must(db.Prepare(`SELECT "id", "updated_at" FROM "messages" WHERE "room_id" = ? AND "created_at" < ? ORDER BY "created_at" DESC LIMIT 40`)),
		full: must(db.Prepare(`SELECT m."id", m."creator_id", m."client_message_id", m."created_at", m."updated_at", t."body", r."name"
			FROM "messages" m JOIN "rooms" r ON r."id" = m."room_id"
			LEFT JOIN "action_text_rich_texts" t ON t."record_type" = 'Message' AND t."name" = 'body' AND t."record_id" = m."id"
			WHERE m."room_id" = ? AND m."created_at" < ? ORDER BY m."created_at" DESC LIMIT 40`)),
		user: must(db.Prepare(`SELECT "name", "updated_at" FROM "users" WHERE "id" = ?`)),
	}
	fmt.Println("go listening", os.Args[3])
	panic(http.ListenAndServe("127.0.0.1:"+os.Args[3], a))
}
