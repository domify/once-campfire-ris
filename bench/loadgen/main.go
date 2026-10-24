// A keep-alive HTTP load generator: CONNS connections, each sending GETs back
// to back for SECONDS, reporting requests/s and latency percentiles.
//
//	go build -o loadgen . && ./loadgen URL COOKIE CONNS SECONDS
package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"slices"
	"strconv"
	"sync"
	"time"
)

func main() {
	url, cookie := os.Args[1], os.Args[2]
	conns, _ := strconv.Atoi(os.Args[3])
	seconds, _ := strconv.Atoi(os.Args[4])
	transport := &http.Transport{MaxIdleConnsPerHost: conns, MaxConnsPerHost: conns, DisableCompression: true}
	client := &http.Client{Transport: transport}
	deadline := time.Now().Add(time.Duration(seconds) * time.Second)

	var mu sync.Mutex
	var all []time.Duration
	failed := 0
	var wg sync.WaitGroup
	for range conns {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var mine []time.Duration
			bad := 0
			for time.Now().Before(deadline) {
				req, _ := http.NewRequest("GET", url, nil)
				req.Header.Set("Cookie", "session_token="+cookie)
				start := time.Now()
				res, err := client.Do(req)
				if err != nil {
					bad++
					continue
				}
				io.Copy(io.Discard, res.Body)
				res.Body.Close()
				if res.StatusCode != 200 {
					bad++
					continue
				}
				mine = append(mine, time.Since(start))
			}
			mu.Lock()
			all = append(all, mine...)
			failed += bad
			mu.Unlock()
		}()
	}
	wg.Wait()
	slices.Sort(all)
	pct := func(p float64) float64 { return float64(all[int(float64(len(all)-1)*p)].Microseconds()) / 1000 }
	fmt.Printf("rps=%.0f n=%d failed=%d min=%.3fms p50=%.3fms p99=%.2fms max=%.2fms\n",
		float64(len(all))/float64(seconds), len(all), failed, pct(0), pct(0.5), pct(0.99), pct(1))
}
