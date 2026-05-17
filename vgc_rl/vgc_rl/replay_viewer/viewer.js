let replay = null
let frameIndex = 0

const els = {
  fileInput: document.getElementById("file-input"),
  replaySelect: document.getElementById("replay-select"),
  reloadList: document.getElementById("reload-list"),
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
  const hpClass = hp > 25 ? "ok" : "low"
  const status = mon.status ? String(mon.status) : "Healthy"
  const boosts = mon.boosts || {}
  const boostBits = ["atk", "def", "spa", "spd", "spe"]
    .filter(k => Number(boosts[k] || 0) !== 0)
    .map(k => `${k}:${Number(boosts[k]) > 0 ? "+" : ""}${boosts[k]}`)
  const boostLine = boostBits.length ? boostBits.join(" ") : "neutral"
  const moves = (mon.moves || []).map(m => m.name || "?").join(" / ")

  return `
    <article class="mon-card">
      <div class="name">${slotLabel}: ${mon.name || "?"}</div>
      <div class="hp ${hpClass}">${hp.toFixed(1)}% HP</div>
      <div class="meta-line">${status} · ${boostLine}</div>
      <div class="meta-line">${mon.item || "—"} · ${mon.ability || "—"}</div>
      <div class="meta-line">${moves}</div>
    </article>
  `
}

function benchLine(party, leads, sideLabel) {
  const busy = new Set(leads || [])
  const parts = []

  party.forEach((mon, i) => {
    if (busy.has(i)) return
    const hp = Number(mon.hpPercentage ?? 0)
    parts.push(`#${i} ${mon.name || "?"} ${hp.toFixed(0)}%`)
  })

  return `${sideLabel} bench: ${parts.length ? parts.join(" · ") : "—"}`
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
    els.alphaBench.textContent = benchLine(st.party_a, st.leads_a, "Alpha")
    els.betaBench.textContent = benchLine(st.party_b, st.leads_b, "Beta")
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

function loadReplay(doc) {
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

async function loadReplayByName(name) {
  const res = await fetch(`/api/replays/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`Failed to load ${name}`)
  return res.json()
}

els.fileInput.addEventListener("change", async e => {
  const file = e.target.files?.[0]
  if (!file) return
  const text = await file.text()
  loadReplay(JSON.parse(text))
})

els.replaySelect.addEventListener("change", async () => {
  const name = els.replaySelect.value
  if (!name) return
  try {
    loadReplay(await loadReplayByName(name))
  } catch (err) {
    alert(String(err))
  }
})

els.reloadList.addEventListener("click", () => refreshReplaySelect())

els.frameSlider.addEventListener("input", () => renderFrame(Number(els.frameSlider.value)))
els.prevFrame.addEventListener("click", () => renderFrame(frameIndex - 1))
els.nextFrame.addEventListener("click", () => renderFrame(frameIndex + 1))

document.addEventListener("keydown", e => {
  if (!replay) return
  if (e.key === "ArrowLeft") renderFrame(frameIndex - 1)
  if (e.key === "ArrowRight") renderFrame(frameIndex + 1)
})

refreshReplaySelect()
