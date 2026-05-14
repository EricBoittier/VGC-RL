# Example doubles teams

Squads target **Pokémon Champions** (`oracle-server` `game: champions`). Showdown mirrors list **six** registered Pokémon per trainer; [`example_teams.json`](example_teams.json) keeps **four** oracle payloads per side in the same party order (slots `0–3`).

Layout matches doubles party size used in `vgc_rl`: **four Pokémon** — indices `0–1` as field leads, `2–3` as bench for switches.

Files:

- `team_alpha_showdown.txt` / `team_beta_showdown.txt` — Pokémon Showdown paste blocks
- `example_teams.json` — oracle batch–compatible Pokémon payloads (`name`, `moves` ×4, `evs`, `item`, `ability`, …)
