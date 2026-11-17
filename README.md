# MW4 Loadouts

Phone web app: pick a game mode, see the best gun and exactly which parts to put on it, based on your own unlock levels.

- Site: https://miguels8.github.io/mw4-loadouts/ (GitHub Pages)
- Data: CODMunity Season 1 Multiplayer builds and Infil "Early game" builds, refreshed daily by `scripts/refresh.py` (no AI).
- Your levels are typed once in the app and saved in your browser only.

## Undo

- Take the site down: repo Settings -> Pages -> Unpublish, or `gh api -X DELETE repos/miguels8/mw4-loadouts/pages`.
- Retire the app: `gh repo archive miguels8/mw4-loadouts`.
- Stop the daily refresh: disable the "refresh" workflow in the Actions tab.
