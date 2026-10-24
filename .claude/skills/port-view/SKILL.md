---
name: port-view
description: Port one Campfire view (an ERB template from reference/app/views) to ris, byte-identical to its golden in vectors/views. Use when asked to port a view, partial or page whose golden and facts are already in vectors/views.
---

# Port a view to ris

You port **one** view (or the few named in your task) so its render is
byte-for-byte the reference's golden. The goldens, the facts and every helper
you need are already in place. Your job is the template, the view class and
its test. Nothing else.

## What you may touch

- `views/templates/<dir>/<name>.html.erb`: the new template.
- `views/<dir>.ri`: the view class. Create it if missing, or add to it.
- `test/views/<dir>_test.ri`: the test.

**Don't touch** `vectors/`, `views/helpers/`, `test/views/golden.ri`,
`views/context.ri`, `rils/template/template.ri`, other views, or the app outside `views/`
(`models/`, `controllers/`, `rils/`, ...). If you need something that isn't there (a helper, a fact, a field on
the context), **stop** and report what is missing. Don't build it yourself.

## Sources (read these first)

1. `reference/app/views/<path>.html.erb`: the Rails original. Port this.
2. `~/contribute/once-campfire-rust/crates/views/templates/<path>.html`: the
   Rust port's (Askama) version. Use it to see which helper call stands for which Rails
   helper.
3. `~/contribute/once-campfire-rust/crates/views/tests/parity_a.rs`: grep for
   the golden's name. It shows how the case is rendered (which user, partial or
   page) and any quirk the comparison corrects for.
4. `vectors/views/<case>.html`: the golden. `vectors/views/facts.json` under
   `cases.<case>` holds the facts for the case.
5. A sibling to copy from: `views/pwa.ri` + `test/views/pwa_test.ri` (partials),
   `views/sessions.ri` + `test/views/sessions_test.ri` (pages in the layout).

## The recipe

1. **Template.** The first line is a comment naming the original:
   `<%# reference/app/views/users/_mention.html.erb %>`. Port the ERB line by
   line. Helpers take `ctx` explicitly and options are an `attrs` chain:
   - `image_tag "x.svg", aria: { hidden: "true" }, class: "c"` becomes
     `image_tag(ctx, "x.svg", attrs.aria_hidden.class("c"))`
   - `translation_button(:key)` becomes `translation_button(ctx, "key")`
   - `platform.x?` becomes `ctx.platform.x`
   - route helpers come from `rils/routes/paths` (`user_ban_path(id)`, ...).
   Before calling a helper, run `grep -n "pub def <name>" views/helpers/*.ri` to
   check its signature.
2. **View class** in `views/<dir>.ri`:
   ```
   # `users/_mention.html.erb`.
   pub class Mention
     getter ctx : ViewContext
     getter user : MentionUser
     def initialize(@ctx : ViewContext, @user : MentionUser)
     end
     Template.def_render("users/_mention.html.erb")   # a partial: gives render : Html
   end
   ```
   For a page in the layout, use `Template.def_page(...)` plus
   `def page(frame = false) : RecordedPage` calling `render_in_layout(@ctx, title, body_class, frame) { |b| render_into(b) }`.
   Put any data the template reads into a small plain class in the same file.
   It holds only what the template uses.
3. **Test** in `views/<dir>_test.ri`. Build the data from
   `golden_case(name)[...]` and the context from `golden_context(name)`, then
   `assert_same(name, golden_page(name), view.render.to_s)` (or `.page.to_s`).
4. **Run** `ris test views/<dir>_test.ri` and fix until it passes. Then run
   `ris fmt views/<dir>.ri views/<dir>_test.ri`.

## golden/b cases (`vectors/views_b/<case>.json`)

Some goldens aren't HTML. They are JSON holding the reference render as a token
stream, the request's context, and the view model as `input`. Model the test
on `test/views/rooms_test.ri`:
```
golden = GoldenB.new(name)          # import test/views/golden_b::*
ctx = golden.context
input = golden.input                # build the view's data from this
golden.assert_dom(View.new(ctx, ...).page.to_s)   # or .render.to_s for a partial
```
`message_view(json)` and `user_view(json)` already decode messages and users.
`assert_dom` compares tokens, so whitespace matters less there. When it fails,
it names the region (title, head, nav, main, footer, sidebar) that differs.

## ris's ERB whitespace (the usual cause of a byte diff)

The ris template engine does **not** trim a line holding only `<% %>` the way
Rails' erubi does:
- `<% code %>` on its own line keeps the indentation before it and the newline after it.
- `<%- code %>` drops the indentation before it and the newline after it. This matches erubi for
  a statement line. **Use this for `each` / `if` / `end` lines.**
- `-%>` also eats the following newline. That is usually one newline too many.
- The engine drops a template file's final newline. Where the golden keeps it (Rails
  does), end the file with one blank line. Don't write `<%= "\n" %>`.
- A partial pulled in with `<% include %>` keeps its final newline. If one is
  rendered both alone and included, end it without a newline and put the newline
  after the `include` in the including template.
- The frame layout keeps the empty line where turbo-rails prints `csrf_meta_tags`,
  as the application layout does.
When the test says "differs at byte N", look at the two excerpts it prints and
adjust exactly that spot.

## ris's prelude (small on purpose)

- When a method is missing (`all?` on Range, say), the error says so. Write a
  `while` loop instead. Don't add to the prelude.
- `String#downcase`/`upcase` are ASCII only, and `strip` differs from Ruby's.
  Avoid both on user data. If the template needs Ruby's exact behaviour, report it.
- `ris doc String` (or any type) lists what exists.
- Match the surrounding code: comments name the Rails original in backticks and
  stay as dense as in sibling files. No raw pointers (`to_unsafe`) in view code.

## Limits

- At most **5** test runs that fail for the same reason. If it still fails,
  stop and report the last diff.
- Your final answer has **at most 5 lines**: the files you created or changed,
  `ris test` result, and anything missing or odd. Don't paste code or diffs.
