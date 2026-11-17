# MW4 Loadouts
Scope: static phone web app (site/) plus a no-AI source refresher (scripts/). No Google Sheet writes.
Tests: `python3 -m unittest discover -s tests -v` and `node --test tests/*.test.mjs`.
Rules: never invent a part or an unlock level (use null, shown as "level not published"); empty level = not entered, never 0; published source dates stay in the data; player levels live only in the browser (the one-time Miguel default is an opt-in import file, not auto-loaded).
Every change after the bootstrap commit goes through a topic branch and a reviewed PR.
Owner of the current work: mw4-webapp-r3. Master rules: /home/miguel/.claude/CLAUDE.md and /home/miguel/RULES.md.
[by:claude-sonnet-5-5/mw4-webapp-r3]
