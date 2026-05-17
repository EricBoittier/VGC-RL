let replay = null
let frameIndex = 0
let simulateDefaults = null

const els = {
  fileInput: document.getElementById("file-input"),
  replaySelect: document.getElementById("replay-select"),
  reloadList: document.getElementById("reload-list"),
  teamAlphaSelect: document.getElementById("team-alpha-select"),
  teamBetaSelect: document.getElementById("team-beta-select"),
  policyAlphaSelect: document.getElementById("policy-alpha-select"),
  policyBetaSelect: document.getElementById("policy-beta-select"),
  simulateSeed: document.getElementById("simulate-seed"),
  simulateGame: document.getElementById("simulate-game"),
  simulateMaxTurns: document.getElementById("simulate-max-turns"),
  simulateVsGreedy: document.getElementById("simulate-vs-greedy"),
  swapTeamsBtn: document.getElementById("swap-teams-btn"),
  randomSeedBtn: document.getElementById("random-seed-btn"),
  optSaveReplay: document.getElementById("opt-save-replay"),
  optNamedPolicies: document.getElementById("opt-named-policies"),
  optAlphaStochastic: document.getElementById("opt-alpha-stochastic"),
  optBetaStochastic: document.getElementById("opt-beta-stochastic"),
  optAllowMega: document.getElementById("opt-allow-mega"),
  optAllowTera: document.getElementById("opt-allow-tera"),
  optRandomBringAlpha: document.getElementById("opt-random-bring-alpha"),
  optRandomBringBeta: document.getElementById("opt-random-bring-beta"),
  optLiveOracle: document.getElementById("opt-live-oracle"),
  simulateBtn: document.getElementById("simulate-btn"),
  simulateStatus: document.getElementById("simulate-status"),
  metaPanel: document.getElementById("meta-panel"),
  frameList: document.getElementById("frame-list"),
  turnTitle: document.getElementById("turn-title"),
  weatherLine: document.getElementById("weather-line"),
  alphaActive: document.getElementById("alpha-active"),
  betaActive: document.getElementById("beta-active"),
  alphaBench: document.getElementById("alpha-bench"),
  betaBench: document.getElementById("beta-bench"),
  alphaChoice: document.getElementById("alpha-choice"),
  betaChoice: document.getElementById("beta-choice"),
  eventLog: document.getElementById("event-log"),
  frameSlider: document.getElementById("frame-slider"),
  prevFrame: document.getElementById("prev-frame"),
  nextFrame: document.getElementById("next-frame"),
}

function tagClass(tag) {
  if (tag === "move") return "tag-move"
  if (tag === "-damage") return "tag-damage"
  if (tag === "switch") return "tag-switch"

  return ""
}

function monCard(mon, slotLabel) {
  const hp = Number(mon.hpPercentage ?? 0)
  const status = mon.status ? String(mon.status) : "Healthy"
  const boosts = mon.boosts || {}
  const boostBits = ["atk", "def", "spa", "spd", "spe"]
    .filter(k => Number(boosts[k] || 0) !== 0)
    .map(k => `${k}:${Number(boosts[k]) > 0 ? "+" : ""}${boosts[k]}`)
  const boostLine = boostBits.length ? boostBits.join(" ") : "neutral"
  const moves = (mon.moves || []).map(m => m.name || "?").join(" / ")
  const species = mon.name || "?"
  const spriteUrl = championsSpriteUrl(species)
  const spriteAttr = spriteUrl ? ` src="${escapeHtml(spriteUrl)}"` : ""

  return `
    <article class="mon-card">
      <div class="mon-card-head">
        <img class="mon-sprite"${spriteAttr} alt="" width="64" height="64" data-species="${escapeHtml(species)}" loading="lazy" referrerpolicy="no-referrer" />
        <div class="mon-card-title">
          <div class="name">${escapeHtml(slotLabel)}: ${escapeHtml(species)}</div>
          ${hpBarHtml(hp)}
        </div>
      </div>
      <div class="meta-line">${escapeHtml(status)} · ${escapeHtml(boostLine)}</div>
      <div class="meta-line">${escapeHtml(mon.item || "—")} · ${escapeHtml(mon.ability || "—")}</div>
      <div class="meta-line">${escapeHtml(moves)}</div>
    </article>
  `
}

function applySprites(root) {
  if (!root) return

  root.querySelectorAll("img[data-species]").forEach(img => {
    const species = img.dataset.species

    if (!species) return

    const known = championsSpriteUrl(species)

    if (known) {
      img.src = known

      return
    }

    resolveChampionsSpriteUrl(species).then(url => {
      if (url) img.src = url
    })
  })
}

function benchChip(mon, index) {
  const hp = Number(mon.hpPercentage ?? 0)
  const species = mon.name || "?"
  const spriteUrl = championsSpriteUrl(species)
  const spriteAttr = spriteUrl ? ` src="${escapeHtml(spriteUrl)}"` : ""

  return `<span class="bench-chip">
    <img class="bench-sprite"${spriteAttr} alt="" width="28" height="28" data-species="${escapeHtml(species)}" loading="lazy" referrerpolicy="no-referrer" />
    <span>#${index} ${escapeHtml(species)}</span>
    ${hpBarHtml(hp)}
  </span>`
}

function benchLine(party, leads, sideLabel) {
  const busy = new Set(leads || [])
  const chips = []

  party.forEach((mon, i) => {
    if (busy.has(i)) return

    chips.push(benchChip(mon, i))
  })

  if (!chips.length) {
    return `<span class="bench-label">${escapeHtml(sideLabel)} bench: —</span>`
  }

  return `<span class="bench-label">${escapeHtml(sideLabel)} bench:</span><span class="bench-chips">${chips.join("")}</span>`
}

function renderMeta(doc) {
  const meta = doc.meta || {}
  const rows = [
    ["Game", doc.game || "—"],
    ["Outcome", doc.outcome || "—"],
    ["Saved", doc.saved_at || "—"],
    ["Phase", meta.phase || "—"],
    ["Round", meta.round != null ? String(meta.round) : "—"],
    ["Episode", meta.episode_index != null ? String(meta.episode_index) : "—"],
    ["Alpha team", meta.team_alpha_key || "—"],
    ["Beta team", meta.team_beta_key || "—"],
    ["Alpha policy", meta.alpha_policy || "—"],
    ["Beta policy", meta.beta_policy || "—"],
    ["Seed", meta.seed != null ? String(meta.seed) : "—"],
    ["Max turns", meta.max_steps != null ? String(meta.max_steps) : "—"],
    ["Alpha mode", meta.alpha_deterministic === false ? "stochastic" : meta.alpha_deterministic === true ? "greedy" : "—"],
    ["Beta mode", meta.beta_deterministic === false ? "stochastic" : meta.beta_deterministic === true ? "greedy" : "—"],
    ["Oracle", meta.fake_oracle === false ? "live" : meta.fake_oracle === true ? "fake" : "—"],
    ["Frames", String((doc.frames || []).length)],
  ]

  els.metaPanel.innerHTML =
    "<dl>" +
    rows.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`).join("") +
    "</dl>"
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

function stateForFrame(doc, index) {
  const frames = doc.frames || []
  if (index < 0 || index >= frames.length) return doc.initial || null

  return frames[index].state_before || doc.initial || null
}

function renderFrame(index) {
  if (!replay) return

  const frames = replay.frames || []
  if (!frames.length) {
    els.turnTitle.textContent = "No turns recorded"

    return
  }

  frameIndex = Math.max(0, Math.min(index, frames.length - 1))
  const frame = frames[frameIndex]
  const st = stateForFrame(replay, frameIndex)

  els.frameSlider.max = String(frames.length - 1)
  els.frameSlider.value = String(frameIndex)

  const kind = frame.kind === "bring" ? "Team preview" : `Turn ${frame.turn ?? frameIndex + 1}`
  els.turnTitle.textContent = kind

  const weather = st?.weather
  const wLeft = st?.weather_turns_left
  els.weatherLine.textContent = weather ? `Weather: ${weather}${wLeft ? ` (${wLeft} turns left)` : ""}` : ""

  if (st) {
    els.alphaActive.innerHTML = [
      monCard(st.party_a[st.leads_a[0]], `A · #${st.leads_a[0]}`),
      monCard(st.party_a[st.leads_a[1]], `B · #${st.leads_a[1]}`),
    ].join("")
    els.betaActive.innerHTML = [
      monCard(st.party_b[st.leads_b[0]], `A · #${st.leads_b[0]}`),
      monCard(st.party_b[st.leads_b[1]], `B · #${st.leads_b[1]}`),
    ].join("")
    applySprites(els.alphaActive)
    applySprites(els.betaActive)
    els.alphaBench.innerHTML = benchLine(st.party_a, st.leads_a, "Alpha")
    els.betaBench.innerHTML = benchLine(st.party_b, st.leads_b, "Beta")
    applySprites(els.alphaBench)
    applySprites(els.betaBench)
  }

  els.alphaChoice.textContent = `Choice: ${frame.alpha_action || "—"}`
  els.betaChoice.textContent = `Choice: ${frame.beta_action || "—"}`

  const events = frame.events || []
  els.eventLog.innerHTML = events
    .map(([tag, body]) => {
      const cls = tagClass(tag)

      return `<li><span class="tag ${cls}">|${escapeHtml(tag)}|</span> ${escapeHtml(body)}</li>`
    })
    .join("")

  document.querySelectorAll("#frame-list li").forEach((li, i) => {
    li.classList.toggle("active", i === frameIndex)
  })
}

function buildTimeline(doc) {
  const frames = doc.frames || []
  els.frameList.innerHTML = frames
    .map((f, i) => {
      const label = f.kind === "bring" ? "Preview" : `T${f.turn ?? i + 1}`

      return `<li><button type="button" data-idx="${i}">${escapeHtml(label)}</button></li>`
    })
    .join("")

  els.frameList.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => renderFrame(Number(btn.dataset.idx)))
  })
}

async function loadReplay(doc) {
  await loadSpriteMap()
  replay = doc
  frameIndex = 0
  renderMeta(doc)
  buildTimeline(doc)
  renderFrame(0)
}

async function fetchReplayList() {
  try {
    const res = await fetch("/api/replays")
    if (!res.ok) return []
    const data = await res.json()

    return data.replays || []
  } catch {
    return []
  }
}

async function refreshReplaySelect() {
  const items = await fetchReplayList()
  const cur = els.replaySelect.value
  els.replaySelect.innerHTML = '<option value="">— saved replays —</option>'
  items.forEach(name => {
    const opt = document.createElement("option")
    opt.value = name
    opt.textContent = name
    els.replaySelect.appendChild(opt)
  })
  if (items.includes(cur)) els.replaySelect.value = cur
}

function fillSelect(select, options, preferred) {
  if (!select) return

  select.innerHTML = ""
  options.forEach(({ value, label }) => {
    const opt = document.createElement("option")
    opt.value = value
    opt.textContent = label
    select.appendChild(opt)
  })

  if (preferred && options.some(o => o.value === preferred)) {
    select.value = preferred
  }
}

function policyOptionsWithAuto(names, preferredAlpha, preferredBeta) {
  const opts = [{ value: "auto", label: "Auto (server default)" }]
  names.forEach(name => opts.push({ value: name, label: name }))

  fillSelect(els.policyAlphaSelect, opts, preferredAlpha || "auto")
  fillSelect(els.policyBetaSelect, opts, preferredBeta || "auto")
}

function applySimulateDefaults(def) {
  if (!def) return

  simulateDefaults = def

  if (els.simulateGame && def.game) els.simulateGame.value = def.game

  if (els.simulateMaxTurns && def.max_turns != null) els.simulateMaxTurns.value = String(def.max_turns)

  if (els.optSaveReplay) els.optSaveReplay.checked = def.save !== false

  if (els.optNamedPolicies) els.optNamedPolicies.checked = def.meta_pool_policies === false

  if (els.optAlphaStochastic) els.optAlphaStochastic.checked = def.alpha_deterministic === false

  if (els.optBetaStochastic) els.optBetaStochastic.checked = def.beta_deterministic === false

  if (els.optAllowMega) els.optAllowMega.checked = def.allow_mega_evolution !== false

  if (els.optAllowTera) els.optAllowTera.checked = def.allow_terastal !== false

  if (els.optRandomBringAlpha) els.optRandomBringAlpha.checked = Boolean(def.random_bring_alpha)

  if (els.optRandomBringBeta) els.optRandomBringBeta.checked = Boolean(def.random_bring_beta)

  if (els.optLiveOracle) {
    els.optLiveOracle.checked = Boolean(def.live_oracle)
    els.optLiveOracle.disabled = false
  }
}

function buildSimulateBody() {
  const teamAlpha = els.teamAlphaSelect?.value
  const teamBeta = els.teamBetaSelect?.value
  const alphaPolicy = els.policyAlphaSelect?.value
  const betaPolicy = els.policyBetaSelect?.value
  const seedRaw = els.simulateSeed?.value?.trim()
  const maxTurnsRaw = els.simulateMaxTurns?.value
  const vsGreedy = els.simulateVsGreedy?.value || ""
  const body = {
    team_alpha_key: teamAlpha,
    team_beta_key: teamBeta,
    save: els.optSaveReplay?.checked !== false,
    game: els.simulateGame?.value || "champions",
    max_turns: maxTurnsRaw ? Number(maxTurnsRaw) : 128,
    meta_pool_policies: els.optNamedPolicies?.checked !== true,
    alpha_stochastic: els.optAlphaStochastic?.checked === true,
    beta_stochastic: els.optBetaStochastic?.checked === true,
    allow_mega_evolution: els.optAllowMega?.checked !== false,
    allow_terastal: els.optAllowTera?.checked !== false,
    random_bring_alpha: els.optRandomBringAlpha?.checked === true,
    random_bring_beta: els.optRandomBringBeta?.checked === true,
    live_oracle: els.optLiveOracle?.checked === true,
  }

  if (alphaPolicy && alphaPolicy !== "auto") body.alpha_policy = alphaPolicy

  if (betaPolicy && betaPolicy !== "auto") body.beta_policy = betaPolicy

  if (seedRaw) body.seed = Number(seedRaw)

  if (vsGreedy) body.vs_greedy = vsGreedy

  return body
}

function teamOptionLabel(team) {
  const species = (team.species || []).slice(0, 3).join(" / ")
  const tail = team.species && team.species.length > 3 ? " …" : ""

  return `${team.label || team.key} · ${species}${tail}`
}

async function fetchTeamsAndPolicies() {
  try {
    const [teamsRes, policiesRes] = await Promise.all([fetch("/api/teams"), fetch("/api/policies")])

    if (!teamsRes.ok || !policiesRes.ok) {
      return null
    }

    const teamsPayload = await teamsRes.json()
    const policiesPayload = await policiesRes.json()

    return {
      teams: teamsPayload.teams || [],
      policies: policiesPayload.policies || [],
      defaults: policiesPayload.defaults || {},
      options: policiesPayload.options || {},
    }
  } catch {
    return null
  }
}

async function initSimulatePanel() {
  const data = await fetchTeamsAndPolicies()

  if (!data) {
    if (els.simulateStatus) {
      els.simulateStatus.textContent = "Simulate API unavailable (open via replay-viewer server)."
      els.simulateStatus.classList.add("error")
    }

    if (els.simulateBtn) els.simulateBtn.disabled = true

    return
  }

  const teamOptions = data.teams.map(t => ({
    value: t.key,
    label: teamOptionLabel(t),
  }))
  const policyOptions = data.policies.map(name => ({ value: name, label: name }))

  fillSelect(els.teamAlphaSelect, teamOptions, data.defaults.team_alpha_key)
  fillSelect(els.teamBetaSelect, teamOptions, data.defaults.team_beta_key)
  policyOptionsWithAuto(data.policies, data.defaults.alpha_policy, data.defaults.beta_policy)
  applySimulateDefaults(data.defaults)

  if (els.simulateVsGreedy && els.optAlphaStochastic && els.optBetaStochastic) {
    const syncGreedy = () => {
      const v = els.simulateVsGreedy.value

      if (v === "alpha") {
        els.optAlphaStochastic.checked = false
        els.optBetaStochastic.checked = true
      } else if (v === "beta") {
        els.optAlphaStochastic.checked = true
        els.optBetaStochastic.checked = false
      }
    }

    els.simulateVsGreedy.addEventListener("change", syncGreedy)
  }

  if (els.simulateStatus) {
    els.simulateStatus.textContent = policyOptions.length ? "Ready — pick teams and simulate." : "No policy zips found in policy directory."
    els.simulateStatus.classList.remove("error")
  }
}

function setSimulateStatus(message, kind) {
  if (!els.simulateStatus) return

  els.simulateStatus.textContent = message
  els.simulateStatus.classList.remove("error", "ok")

  if (kind) els.simulateStatus.classList.add(kind)
}

async function runSimulate() {
  if (!els.simulateBtn) return

  const body = buildSimulateBody()

  els.simulateBtn.disabled = true
  setSimulateStatus("Running battle…", null)

  try {
    const res = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    const payload = await res.json()

    if (!res.ok) {
      throw new Error(payload.error || `Simulate failed (${res.status})`)
    }

    await loadReplay(payload.replay)
    await refreshReplaySelect()

    if (payload.saved_as && els.replaySelect) {
      els.replaySelect.value = payload.saved_as
    }

    const outcome = payload.replay?.outcome || "done"
    setSimulateStatus(`Battle finished · ${outcome}${payload.saved_as ? ` · saved ${payload.saved_as}` : ""}`, "ok")
  } catch (err) {
    setSimulateStatus(String(err), "error")
  } finally {
    els.simulateBtn.disabled = false
  }
}

async function loadReplayByName(name) {
  const res = await fetch(`/api/replays/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`Failed to load ${name}`)

  return res.json()
}

els.fileInput.addEventListener("change", async e => {
  const file = e.target.files?.[0]
  if (!file) return
  const text = await file.text()
  await loadReplay(JSON.parse(text))
})

els.replaySelect.addEventListener("change", async () => {
  const name = els.replaySelect.value
  if (!name) return

  try {
    await loadReplay(await loadReplayByName(name))
  } catch (err) {
    alert(String(err))
  }
})

els.reloadList.addEventListener("click", () => refreshReplaySelect())

if (els.simulateBtn) {
  els.simulateBtn.addEventListener("click", () => runSimulate())
}

if (els.swapTeamsBtn) {
  els.swapTeamsBtn.addEventListener("click", () => {
    if (!els.teamAlphaSelect || !els.teamBetaSelect) return

    const a = els.teamAlphaSelect.value
    const b = els.teamBetaSelect.value
    const pa = els.policyAlphaSelect?.value
    const pb = els.policyBetaSelect?.value

    els.teamAlphaSelect.value = b
    els.teamBetaSelect.value = a

    if (els.policyAlphaSelect && els.policyBetaSelect && pa && pb) {
      els.policyAlphaSelect.value = pb
      els.policyBetaSelect.value = pa
    }
  })
}

if (els.randomSeedBtn) {
  els.randomSeedBtn.addEventListener("click", () => {
    if (!els.simulateSeed) return

    els.simulateSeed.value = String(Math.floor(Math.random() * 2_147_483_647))
  })
}

els.frameSlider.addEventListener("input", () => renderFrame(Number(els.frameSlider.value)))
els.prevFrame.addEventListener("click", () => renderFrame(frameIndex - 1))
els.nextFrame.addEventListener("click", () => renderFrame(frameIndex + 1))

document.addEventListener("keydown", e => {
  if (!replay) return
  if (e.key === "ArrowLeft") renderFrame(frameIndex - 1)
  if (e.key === "ArrowRight") renderFrame(frameIndex + 1)
})

loadSpriteMap().then(() => {
  refreshReplaySelect()
  initSimulatePanel()

  if (replay) renderFrame(frameIndex)
})
