import type { BatchRequestBody } from "./batch-types.js"

export const ragingBoltVsFlutterManeSingle: BatchRequestBody = {
  game: "sv",
  requests: [
    {
      kind: "single",
      field: {},
      attacker: {
        name: "Raging Bolt",
        moves: [{ name: "Thunderbolt" }, { name: "Thunderclap" }, { name: "Draco Meteor" }, { name: "Protect" }],
        activeMovePosition: 1
      },
      defender: {
        name: "Flutter Mane",
        moves: [{ name: "Moonblast" }, { name: "Shadow Ball" }, { name: "Dazzling Gleam" }, { name: "Protect" }]
      }
    }
  ]
}
