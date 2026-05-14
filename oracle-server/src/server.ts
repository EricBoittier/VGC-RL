import { createServer, IncomingMessage, ServerResponse } from "node:http"
import type { BatchRequestBody } from "./batch-types.js"
import { handleOracleBatch } from "./run-batch.js"

const MAX_BODY_BYTES = 10 * 1024 * 1024

function sendJson(res: ServerResponse, status: number, body: unknown) {
  const payload = JSON.stringify(body)

  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Access-Control-Allow-Origin": "*"
  })

  res.end(payload)
}

async function readJsonBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  let total = 0

  for await (const chunk of req) {
    const buf = chunk instanceof Buffer ? chunk : Buffer.from(chunk)

    total += buf.length

    if (total > MAX_BODY_BYTES) {
      throw new Error("request body too large")
    }

    chunks.push(buf)
  }

  const raw = Buffer.concat(chunks).toString("utf8")

  if (!raw.length) return undefined

  return JSON.parse(raw) as unknown
}

function isBatchBody(value: unknown): value is BatchRequestBody {
  if (!value || typeof value !== "object") return false

  const o = value as Record<string, unknown>

  if (o.game !== "sv" && o.game !== "champions") return false

  if (!Array.isArray(o.requests)) return false

  return true
}

export function createOracleHttpServer() {
  return createServer(async (req, res) => {
    try {
      if (req.method === "GET" && req.url === "/health") {
        sendJson(res, 200, { ok: true })

        return
      }

      if (req.method === "POST" && req.url === "/batch") {
        const parsed = await readJsonBody(req)

        if (!isBatchBody(parsed)) {
          sendJson(res, 400, { error: "expected JSON body { game, requests }" })

          return
        }

        const out = handleOracleBatch(parsed)

        sendJson(res, 200, out)

        return
      }

      sendJson(res, 404, { error: "not found" })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)

      sendJson(res, 400, { error: message })
    }
  })
}
