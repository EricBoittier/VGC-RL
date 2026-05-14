import { createOracleHttpServer } from "./server.js"

const port = Number(process.env.PORT ?? "8765")

createOracleHttpServer().listen(port, () => {
  console.error(`vgc-oracle-server listening on ${port}`)
})
