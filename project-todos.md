# Todo Manager UI Changes

## 1. Reset display numbering to start from 1
Todos and reminders are displayed with their persistent stored `id` (e.g., `[15]`).
Change all list displays to use the item's position (1, 2, 3...) instead of `id`.
Affects: `cmd_list`, `cmd_todos`, `cmd_remind`, `_print_reminders`.

## 2. Remove space-padding in reminder brackets
Reminders currently display as `[ 2]` (right-aligned with padding).
Change to `[2]` (no padding).
Affects: `_print_reminders`.

## 3. Simplify reminder date line format
Currently: `due 2026-05-22  due in 25d`
Change to: `2026-05-22, due in 25d`
Affects: `_print_reminders` and `urgency_label` output composition.

## 4. Truncate priority recommendation to one line
`get_priority_recommendation` returns a multi-sentence paragraph.
Either update the system prompt to instruct Claude to respond in one sentence,
or truncate the result to the first line before printing.
Affects: everywhere `get_priority_recommendation` result is printed.

## 5. Make morning auto-run interactive (allow new inputs)
`cmd_remind` currently shows a summary and exits.
Change it to show the summary, then drop into the add-new-todos / add-new-reminders
prompts (reuse the tail of `cmd_todos`: steps 3 and 4 — new todos, new reminders).
Affects: `cmd_remind`, `todo_remind.sh` (the Terminal window command may need `read` removed or kept).
