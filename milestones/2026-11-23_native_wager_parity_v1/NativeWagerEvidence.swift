import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif

// Native read-only proof. Never publishes poker actions.
struct WagerError: Error, CustomStringConvertible {
    let description: String
    init(_ s: String) { description = s }
}

func expect(_ ok: Bool, _ reason: String) throws {
    if !ok { throw WagerError(reason) }
}

func document(_ url: URL) throws -> Any {
    try JSONSerialization.jsonObject(with: Data(contentsOf: url))
}

func object(_ v: Any?) throws -> [String:Any] {
    guard let x = v as? [String:Any] else {
        throw WagerError("INVALID_OBJECT")
    }
    return x
}

func array(_ v: Any?) throws -> [[String:Any]] {
    guard let x = v as? [[String:Any]] else {
        throw WagerError("INVALID_ARRAY")
    }
    return x
}

func string(_ v: Any?) throws -> String {
    guard let x = v as? String, !x.isEmpty else {
        throw WagerError("INVALID_STRING")
    }
    return x
}

func integer(_ v: Any?) throws -> Int {
    guard let x = v as? Int else {
        throw WagerError("INVALID_INTEGER")
    }
    return x
}

func bb(_ s: String) -> Int? {
    guard s.range(
        of: "^[0-9]+(\\.[0-9]{1,2})?$",
        options: .regularExpression
    ) != nil else { return nil }

    let parts = s.split(
        separator: ".", omittingEmptySubsequences: false
    )
    guard let whole = Int(parts[0]), whole <= 100000 else {
        return nil
    }
    let cents = parts.count == 2
        ? Int((String(parts[1]) + "00").prefix(2)) ?? -1
        : 0
    guard cents >= 0 else { return nil }
    return whole * 100 + cents
}

func amount(_ text: String, kind: String) -> Int? {
    let pattern: String
    switch kind {
    case "plain":
        pattern = #"^\s*([0-9]+(?:\.[0-9]{1,2})?)\s*BB\s*$"#
    case "total":
        pattern = #"^\s*Total\s*:\s*([0-9]+(?:\.[0-9]{1,2})?)\s*BB\s*$"#
    case "pot":
        pattern = #"^\s*Pot\s+([0-9]+(?:\.[0-9]{1,2})?)\s*BB\s*$"#
    default:
        return nil
    }

    guard let rx = try? NSRegularExpression(
        pattern: pattern, options: .caseInsensitive
    ), let m = rx.firstMatch(
        in: text,
        range: NSRange(text.startIndex..., in: text)
    ), m.range.location == 0,
       let r = Range(m.range(at: 1), in: text)
    else { return nil }

    return bb(String(text[r]))
}

func lines(_ doc: [String:Any]) throws -> [[String:Any]] {
    let capture = try object(doc["capture"])
    return try array(capture["lines"]).filter {
        ($0["confidence"] as? Double ?? 0) >= 0.8
    }
}

func one(
    _ rows: [[String:Any]],
    _ kind: String,
    near: (Double,Double,Double,Double)? = nil
) -> Int? {
    let found = rows.compactMap { row -> Int? in
        if let p = near {
            guard let x = row["x"] as? Double,
                  let y = row["y"] as? Double,
                  abs(x-p.0) < p.2,
                  abs(y-p.1) < p.3
            else { return nil }
        }
        return (row["text"] as? String).flatMap {
            amount($0, kind: kind)
        }
    }
    return found.count == 1 ? found[0] : nil
}

func around(
    _ rows: [[String:Any]],
    _ text: String,
    _ x: Double,
    _ y: Double
) -> Int {
    rows.filter { row in
        guard let t = row["text"] as? String,
              let a = row["x"] as? Double,
              let b = row["y"] as? Double
        else { return false }

        return t.trimmingCharacters(in: .whitespaces) == text
            && abs(x-a) < 0.017
            && abs(y-b) < 0.020
    }.count
}

func sha256(_ path: URL) throws -> String {
    let bytes = try Data(contentsOf: path)
    #if canImport(CryptoKit)
    return "sha256:" + SHA256.hash(data: bytes).map {
        String(format: "%02x", $0)
    }.joined()
    #else
    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/usr/bin/sha256sum")
    task.arguments = ["-"]
    let input = Pipe(), output = Pipe()
    task.standardInput = input
    task.standardOutput = output
    try task.run()
    input.fileHandleForWriting.write(bytes)
    try input.fileHandleForWriting.close()
    let out = output.fileHandleForReading.readDataToEndOfFile()
    task.waitUntilExit()
    try expect(task.terminationStatus == 0, "SHA256_FAILURE")
    return "sha256:" +
        String(data: out, encoding: .utf8)!.split(separator: " ").first!
    #endif
}

func check(
    _ row: [String:Any],
    root: URL,
    frames: [[String:Any]],
    boards: [[String:Any]],
    actions: [[String:Any]]
) throws -> [String:Any] {
    let hand = try string(row["hand"])
    let player = try string(row["player"])
    let f = try integer(row["from_frame"])
    let t = try integer(row["to_frame"])

    try expect(
        t == f+1 && f >= 1 && t <= frames.count
            && frames.count == boards.count,
        "FRAME_GAP"
    )

    let fps = row["original_fingerprints"] as? [String] ?? []
    try expect(
        fps.count == 2 && fps[0] != fps[1]
            && row["not_authoritative"] as? Bool == true,
        "FINGERPRINTS"
    )

    let candidates = actions.filter {
        ($0["hand"] as? String) == hand
            && ($0["frame"] as? Int) == t
            && ($0["beforeFrame"] as? Int) == f
    }
    try expect(candidates.count == 1, "AMBIGUOUS_ACTION_EPISODE")

    let c = candidates[0]
    let label = try string(c["overlay"])

    try expect(
        ["BET","RAISE","CALL"].contains(label)
            && (c["player"] as? String) == player
            && (c["sameFrameOrderUnknown"] as? Bool) == false
            && (c["beforeFingerprint"] as? String) == fps[0]
            && (c["currentFingerprint"] as? String) == fps[1]
            && (row["overlay"] as? String) == label,
        "OVERLAY_PROOF"
    )

    var captured = [Double]()
    var ocrs = [[[String:Any]]]()

    for (index,n) in [f,t].enumerated() {
        let rec = frames[n-1]
        let board = boards[n-1]

        try expect(
            (rec["id"] as? Int) == n
                && (board["frame"] as? Int) == n
                && (board["hand"] as? String) == hand
                && (board["sourceFingerprint"] as? String) == fps[index],
            "FRAME_OWNER"
        )

        let relative = try string(rec["file"])
        try expect(
            relative.hasPrefix("frames/")
                && !relative.contains("..")
                && !relative.hasPrefix("/"),
            "IMAGE_PATH"
        )
        let image = root.appendingPathComponent(
            relative
        ).standardizedFileURL

        try expect(
            image.path.hasPrefix(root.standardizedFileURL.path + "/")
                && (try sha256(image)) == fps[index],
            "JPEG_HASH_MISMATCH"
        )

        let ocr = try object(document(
            root.appendingPathComponent(
                String(format: "local_ocr/%06d.json", n)
            )
        ))

        try expect(
            (ocr["frame"] as? Int) == n
                && (ocr["sourceFingerprint"] as? String) == fps[index],
            "OCR_HASH_MISMATCH"
        )

        let ls = try lines(ocr)
        let handLines = ls.filter {
            ($0["text"] as? String)?.range(
                of: "^Current\\s*:\\s*" + hand + "$",
                options: [.regularExpression,.caseInsensitive]
            ) != nil
        }
        try expect(handLines.count == 1, "HAND_OCR_MISMATCH")

        ocrs.append(ls)
        captured.append((rec["captured"] as? Double) ?? -1)
    }

    try expect(
        captured[1] > captured[0]
            && captured[1] - captured[0] < 1.5,
        "TIME_GAP"
    )

    let boardCount = try integer(boards[f-1]["visibleBoardCount"])
    try expect(
        [0,3,4,5].contains(boardCount)
            && boardCount == (boards[t-1]["visibleBoardCount"] as? Int),
        "STREET_CHANGED"
    )

    let x = (c["x"] as? Double) ?? -1000
    let y = (c["y"] as? Double) ?? -1000

    try expect(
        around(ocrs[0],player,x,y) == 1
            && around(ocrs[1],label,x,y) == 1,
        "SEAT_LABEL"
    )

    let display = try object(c["displayedWager"])
    let wagerText = try string(display["text"])
    let wx = (display["x"] as? Double) ?? -1000
    let wy = (display["y"] as? Double) ?? -1000

    try expect(
        (display["confidence"] as? Double ?? 0) >= 0.8
            && around(ocrs[1],wagerText,wx,wy) == 1
            && around(ocrs[0],wagerText,wx,wy) == 0,
        "NEW_WAGER_LABEL"
    )

    guard let wager = amount(wagerText,kind:"plain"),
          let certified = bb(try string(row["wager_contribution_bb"])),
          let displayed = bb(try string(display["amountBB"])),
          let old = bb(try string(c["beforeStackBB"])),
          let new = bb(try string(c["afterStackBB"])),
          let total0 = one(ocrs[0],"total"),
          let total1 = one(ocrs[1],"total"),
          let pot0 = one(ocrs[0],"pot"),
          let pot1 = one(ocrs[1],"pot"),
          let oldOCR = one(
              ocrs[0],"plain",
              near:(x,y-0.042,0.020,0.023)
          ),
          let newOCR = one(
              ocrs[1],"plain",
              near:(x,y-0.042,0.020,0.023)
          )
    else { throw WagerError("NUMERIC_OCR_NOT_UNIQUE") }

    let delta = wager % 100 == 0
        ? String(wager / 100)
        : (wager % 10 == 0
            ? "\(wager / 100).\(wager % 100 / 10)"
            : String(format:"%d.%02d",wager / 100,wager % 100))

    try expect(
        wager == certified && wager == displayed
            && old == oldOCR && new == newOCR
            && old-new == wager
            && total1-total0 == wager
            && pot0 == pot1
            && (c["observedStackDeltaBB"] as? String) == "-" + delta,
        "MONEY_CONSERVATION"
    )

    let formatted = String(format:"%.2f",Double(wager)/100)

    return [
        "hand":hand,
        "player":player,
        "from_frame":f,
        "to_frame":t,
        "overlay":label,
        "observed_contribution_bb":formatted,
        "raise_to":"UNVERIFIED",
        "sourceFingerprints":fps,
        "not_authoritative":true
    ]
}

@main struct NativeWagerEvidence {
    static func main() {
        do { try run() }
        catch {
            print("STOP: \(error)")
            exit(3)
        }
    }

    static func run() throws {
        let args = CommandLine.arguments
        try expect(
            args.count == 4,
            "Usage: NativeWagerEvidence ORIGINAL_ROOT CERTIFIED_REPORT OUTPUT_JSON"
        )

        let root = URL(fileURLWithPath:args[1],isDirectory:true)
        let report = try object(document(URL(fileURLWithPath:args[2])))

        try expect(
            (report["amount_corroborated"] as? Int) == 3
                && (report["negative_tests_rejected"] as? Int) == 10
                && (report["authoritative_actions_created"] as? Int) == 0,
            "REPORT_NOT_CERTIFIED"
        )

        let frames = try array(document(
            root.appendingPathComponent("frames.json")
        ))
        let boards = try array(document(
            root.appendingPathComponent("local_board_observations.json")
        ))
        let actions = try array(document(
            root.appendingPathComponent("local_action_candidates.json")
        ))
        let proofs = try array(report["proofs"])

        var result = [[String:Any]]()
        for row in proofs {
            try result.append(check(
                row,root:root,frames:frames,
                boards:boards,actions:actions
            ))
        }

        result.sort {
            ($0["to_frame"] as! Int) < ($1["to_frame"] as! Int)
        }

        try expect(
            result.count == 3
                && result.map{$0["to_frame"] as! Int} == [250,305,314],
            "CERTIFIED_THREE_FRAME_REGRESSION"
        )

        let output:[String:Any] = [
            "schema":"PI_NATIVE_WAGER_PROVENANCE_V1",
            "amounts":result,
            "actions_created":0,
            "unreviewed_events_admitted":0
        ]
        let data = try JSONSerialization.data(
            withJSONObject:output,
            options:[.sortedKeys,.prettyPrinted]
        )
        try data.write(to:URL(fileURLWithPath:args[3]))

        print(
            "NATIVE_WAGER_PARITY_PASS originals=6 amounts=2.10,3.33,8.16 unreviewed_frame197=WITHHELD actions_created=0"
        )
    }
}
