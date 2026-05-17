let spriteBySpecies = null
let spriteByFile = null
let spriteMapPromise = null

function formSuffix(name) {
  const parts = String(name || "").split("-")

  if (parts.length === 1) return ""

  const rest = parts.slice(1)

  if (rest[0] === "Mega") {
    if (rest.length === 1) return "Mega"

    if (rest[1] === "X" || rest[1] === "Y") return `Mega ${rest[1]}`
  }

  if (rest[0] === "Alola" || rest[0] === "Galar" || rest[0] === "Hisui") return rest[0]

  if (rest[0] === "Paldea" && rest.length >= 2) {
    return `Paldea ${rest[1].charAt(0).toUpperCase()}${rest[1].slice(1)}`
  }

  if (rest[0] === "Rotom") return rest[1]

  if ((rest[0] === "F" && rest[1] === "Mega") || rest[0] === "F") return "Female"

  if ((rest[0] === "M" && rest[1] === "Mega") || rest[0] === "M") return "Male"

  return rest.join("-")
}

function spriteFileFromDex(dex, form) {
  const candidates = []

  if (form) candidates.push(`Menu CP ${String(dex).padStart(4, "0")}-${form}.png`)

  candidates.push(`Menu CP ${String(dex).padStart(4, "0")}.png`)

  for (const c of candidates) {
    if (spriteByFile && spriteByFile[c]) return c
  }

  const prefix = `Menu CP ${String(dex).padStart(4, "0")}`
  const matches = Object.keys(spriteByFile || {})
    .filter(f => f.startsWith(prefix))
    .sort()

  if (matches.length === 1) return matches[0]

  if (form === "Mega") {
    const mega = matches.find(f => f.includes("-Mega") && !f.includes("Female") && !f.includes("Male"))

    if (mega) return mega
  }

  return matches[0] || null
}

async function dexForSpecies(name) {
  const base = String(name || "")
    .split("-")[0]
    .toLowerCase()
    .replace(/'/g, "")
    .replace(/\./g, "")
  const slugs = [base, String(name).toLowerCase().replace(/ /g, "-")]

  for (const slug of slugs) {
    try {
      const res = await fetch(`https://pokeapi.co/api/v2/pokemon/${slug}`)

      if (res.ok) return (await res.json()).id
    } catch {
      /* ignore */
    }
  }

  try {
    const res = await fetch(`https://pokeapi.co/api/v2/pokemon-species/${base}`)

    if (res.ok) return (await res.json()).id
  } catch {
    /* ignore */
  }

  return null
}

function loadSpriteMap() {
  if (spriteMapPromise) return spriteMapPromise

  spriteMapPromise = fetch("champions_sprite_map.json")
    .then(res => {
      if (!res.ok) throw new Error("sprite map missing")

      return res.json()
    })
    .then(data => {
      if (data && data.bySpecies) {
        spriteBySpecies = data.bySpecies
        spriteByFile = data.byFile || {}
      } else {
        spriteBySpecies = data
        spriteByFile = {}
      }

      return data
    })
    .catch(err => {
      console.warn("sprite map failed to load", err)
      spriteBySpecies = {}
      spriteByFile = {}

      return null
    })

  return spriteMapPromise
}

function spriteProxyUrl(speciesName) {
  const name = String(speciesName || "").trim()

  if (!name) return null

  return `/sprites/${encodeURIComponent(name)}`
}

function championsSpriteUrl(speciesName) {
  const name = String(speciesName || "").trim()

  if (!name || !spriteBySpecies) return null

  if (!spriteBySpecies[name]) return null

  return spriteProxyUrl(name)
}

async function resolveChampionsSpriteUrl(speciesName) {
  await loadSpriteMap()

  const cached = championsSpriteUrl(speciesName)

  if (cached) return cached

  const name = String(speciesName || "").trim()

  if (!name) return null

  const dex = await dexForSpecies(name)

  if (!dex) return null

  const file = spriteFileFromDex(dex, formSuffix(name))

  if (!file || !spriteByFile[file]) return null

  spriteBySpecies[name] = spriteByFile[file]

  return spriteProxyUrl(name)
}

function hpTone(hp) {
  if (hp > 75) return "high"
  if (hp > 15) return "mid"

  return "low"
}

function hpBarHtml(hp) {
  const pct = Math.max(0, Math.min(100, Number(hp) || 0))
  const tone = hpTone(pct)

  return (
    '<div class="hp-row hp-' +
    tone +
    '">' +
    '<div class="hp-bar" role="progressbar" aria-valuenow="' +
    pct.toFixed(1) +
    '" aria-valuemin="0" aria-valuemax="100">' +
    '<div class="hp-bar-lost"></div>' +
    '<div class="hp-bar-fill" style="width: ' +
    pct.toFixed(1) +
    '%"></div>' +
    "</div>" +
    '<span class="hp-label">' +
    pct.toFixed(1) +
    "%</span>" +
    "</div>"
  )
}
