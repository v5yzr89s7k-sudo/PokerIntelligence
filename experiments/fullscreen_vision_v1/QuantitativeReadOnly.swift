import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif

struct OCRLine {
    let text: String
    let x: Double
    let y: Double
    let confidence: Double
}
struct SeatAnchor {
    let visibleLabel: String
    let x: Double
    let y: Double
    let knownName: String?
}
struct Amount {
    let mills: Int
    let line: OCRLine
    var display: String { formatBB(mills) }
}
struct NumericSnapshot {
    let hand: String
    let frame: Int
    let sourceFingerprint: String
    let pot: Amount?
    let total: Amount?
    let wagers: [(Amount, SeatAnchor)]
    let extraneous: [Amount]
    let status: String
    let expectedOutstanding: Int?
    func jsonValue(unknownSeatAnchors:[(Double,Double)] = []) -> [String: Any] {
        var d: [String:Any] = ["hand":hand,"frame":frame,"source_fingerprint":sourceFingerprint,"status":status,"not_authoritative":true]
        if let pot = pot { d["pot_bb"] = pot.display }
        if let total = total { d["total_bb"] = total.display }
        if let e = expectedOutstanding { d["expected_outstanding_bb"] = formatBB(e) }
        d["wagers"] = wagers.map { amount,seat in
            // Unknown physical seats are geometric blockers, not names.
            // A chip near an unknown seat cannot inherit a nearby name.
            let distance=hypot(amount.line.x-seat.x,amount.line.y-seat.y)
            let ambiguous=unknownSeatAnchors.contains { unknown in
                hypot(amount.line.x-unknown.0,amount.line.y-unknown.1) <= distance+0.020
            }
            let verified=seat.knownName != nil && !ambiguous
            var w:[String:Any] = ["amount_bb":amount.display,"source_text":amount.line.text,"x":amount.line.x,"y":amount.line.y,"seat_label":ambiguous ? "UNVERIFIED_SEAT" : seat.visibleLabel,"identity_status":verified ? "EARLIER_FRAME_VERIFIED" : "UNRESOLVED"]
            if verified,let name=seat.knownName {w["player"]=name}
            return w
        }
        d["unassigned_numeric_labels"] = extraneous.map { ["amount_bb":$0.display,"x":$0.line.x,"y":$0.line.y] as [String : Any] }
        return d
    }
}
func formatBB(_ mills: Int) -> String {
    let sign = mills < 0 ? "-" : ""
    let whole = abs(mills) / 1000
    let r = abs(mills) % 1000
    if r == 0 { return "\(sign)\(whole)" }
    var s = String(format:"%03d",r)
    while s.hasSuffix("0") { s.removeLast() }
    return "\(sign)\(whole).\(s)"
}
func parseBB(_ text: String) -> Int? {
    let p = text.split(separator:".", omittingEmptySubsequences:false)
    guard p.count <= 2 && !p.isEmpty && p[0].allSatisfy({$0.isNumber}), !p[0].isEmpty,
          let whole = Int(p[0]), whole < 1_000_000 else { return nil }
    var part=0
    if p.count == 2 {
        guard p[1].count > 0 && p[1].count <= 3 && p[1].allSatisfy({$0.isNumber}), let v=Int(p[1]) else { return nil }
        part = v * (p[1].count == 1 ? 100 : (p[1].count == 2 ? 10 : 1))
    }
    return whole*1000+part
}
let rxPot = try! NSRegularExpression(pattern:"^Pot\\s*:?\\s*([0-9]+(?:\\.[0-9]{1,3})?)\\s*BB$", options:[.caseInsensitive])
let rxTotal = try! NSRegularExpression(pattern:"^Total\\s*:\\s*([0-9]+(?:\\.[0-9]{1,3})?)\\s*BB$", options:[.caseInsensitive])
let rxAmount = try! NSRegularExpression(pattern:"^([0-9]+(?:\\.[0-9]{1,3})?)\\s*BB$", options:[.caseInsensitive])
let rxHand = try! NSRegularExpression(pattern:"^Current:\\s*([0-9]{8,12})$")
func captureMatch(_ pattern: NSRegularExpression,_ text:String) -> String? {
    let range = NSRange(text.startIndex..<text.endIndex,in:text)
    guard let m = pattern.firstMatch(in:text,range:range),m.range.location != NSNotFound,m.range.length == range.length,
          m.numberOfRanges > 1,let r = Range(m.range(at:1),in:text) else {return nil}
    return String(text[r])
}
func jsonFile(_ path:URL) throws -> Any {
    try JSONSerialization.jsonObject(with:Data(contentsOf:path))
}
func parseLines(_ doc: [String:Any]) -> [OCRLine] {
    guard let capture = doc["capture"] as? [String:Any],let lines = capture["lines"] as? [[String:Any]] else {return []}
    return lines.compactMap { line in
        guard let t=line["text"] as? String,let x=line["x"] as? Double,let y=line["y"] as? Double,let c=line["confidence"] as? Double else{return nil}
        return OCRLine(text:t.trimmingCharacters(in:.whitespacesAndNewlines),x:x,y:y,confidence:c)
    }
}
let rxSeatLabel = try! NSRegularExpression(pattern:"^[A-Za-z][A-Za-z0-9_ '\u{2019}\u{002D}]{1,30}$")
// Action overlays replace nameplates, but are never player identities.
let nonIdentityLabels: Set<String> = [
    "FOLD", "CALL", "RAISE", "RAISER", "CHECK", "BET", "ALLIN",
    "ANTE", "ANTER", "POSTSB", "POSTBB", "POSTANTE", "SB", "BB",
    "WINNER", "WIN", "DONTSHOW", "SHOW", "SHOWCARDS", "MUCK",
    "SITOUT", "SITTINGOUT", "TIMEBANK", "WAITING"
]
func isInterfaceLabel(_ text: String) -> Bool {
    let normalized = text.uppercased().filter { $0.isLetter || $0.isNumber }
    return nonIdentityLabels.contains(normalized)
}
func seatText(_ text: String) -> Bool {
    let range=NSRange(text.startIndex..<text.endIndex,in:text)
    return rxSeatLabel.firstMatch(in:text,range:range) != nil
}
func extractSnapshot(_ doc:[String:Any], knownNames: [String], pastSeats: [String:(Double,Double)] = [:]) -> NumericSnapshot? {
    guard let frame=doc["frame"] as? Int,let fingerprint=doc["sourceFingerprint"] as? String else {return nil}
    let lines = parseLines(doc)
    let handIDs = lines.compactMap { captureMatch(rxHand,$0.text) }
    guard handIDs.count == 1 else{return nil}
    let hand=handIDs[0]
    let pot = lines.compactMap { line -> Amount? in
        guard line.confidence >= 0.8,abs(line.x-0.5)<0.075,abs(line.y-0.405)<0.09,
              let v=captureMatch(rxPot,line.text).flatMap(parseBB) else{return nil}
        return Amount(mills:v,line:line)
    }
    let total = lines.compactMap { line -> Amount? in
        guard line.confidence >= 0.8,abs(line.x-0.5)<0.075,abs(line.y-0.59)<0.08,
              let v=captureMatch(rxTotal,line.text).flatMap(parseBB) else{return nil}
        return Amount(mills:v,line:line)
    }
    var anchors = [SeatAnchor]()
    for label in lines where label.confidence >= 0.8 {
        guard seatText(label.text) && captureMatch(rxAmount,label.text) == nil && captureMatch(rxPot,label.text) == nil &&
              captureMatch(rxTotal,label.text) == nil else {continue}
        let stacks = lines.filter { am in
            am.confidence >= 0.8 && captureMatch(rxAmount,am.text) != nil &&
            abs(am.x-label.x)<0.034 && (label.y-am.y) > 0.022 && (label.y-am.y) < 0.072
        }
        if stacks.count != 1 {continue}
        // A verified player name requires the earlier hand-scoped roster
        // and a matching physical seat position, not an action overlay.
        let prior = pastSeats[label.text]
        let name: String? = (!isInterfaceLabel(label.text) &&
            knownNames.contains(label.text) && prior != nil &&
            hypot(label.x-prior!.0,label.y-prior!.1)<0.018)
            ? label.text : nil
        let visible = name ?? (isInterfaceLabel(label.text)
            ? "UNVERIFIED_SEAT" : "OCR_NAME_CANDIDATE:"+label.text)
        anchors.append(SeatAnchor(visibleLabel:visible,x:label.x,y:label.y,knownName:name))
    }
    // Past seats are valid only when a roster was established on a *previous* frame.
    for name in pastSeats.keys.sorted() {
        // Even a corrupted roster cannot promote a UI action to a name.
        guard !isInterfaceLabel(name),let point=pastSeats[name] else {continue}
        anchors.removeAll { a in
            a.knownName == nil && hypot(a.x-point.0,a.y-point.1)<0.018
        }
        if !anchors.contains(where:{$0.knownName == name}) {
            anchors.append(SeatAnchor(visibleLabel:name,x:point.0,y:point.1,knownName:name))
        }
    }
    var wagers = [(Amount,SeatAnchor)]()
    var extraneous = [Amount]()
    for line in lines where line.confidence >= 0.8 && line.x >= 0.24 && line.x <= 0.76 && line.y >= 0.28 && line.y <= 0.75 {
        guard let s=captureMatch(rxAmount,line.text),let milli=parseBB(s) else {continue}
        // Do not confuse seat stack labels with wager chips.
        if lines.contains(where: { l in
            l.confidence >= 0.8 && seatText(l.text) && captureMatch(rxAmount,l.text) == nil &&
            captureMatch(rxPot,l.text) == nil && captureMatch(rxTotal,l.text) == nil &&
            abs(l.x-line.x)<0.034 && (l.y-line.y)>0.022 && (l.y-line.y)<0.072
        }) { continue }
        let amount=Amount(mills:milli,line:line)
        let nearest = anchors.map { anchor in
            (anchor,hypot(line.x-anchor.x,line.y-anchor.y))
        }.sorted {a,b in a.1 < b.1}
        if let first=nearest.first,first.1 <= 0.245 &&
           (nearest.count == 1 || nearest[1].1-first.1 >= 0.020) {
            wagers.append((amount,first.0))
        } else { extraneous.append(amount) }
    }
    let p=pot.count == 1 ? pot[0] : nil
    let t=total.count == 1 ? total[0] : nil
    var expected: Int? = nil
    var status="INCOMPLETE_OCR"
    if pot.count > 1 || total.count > 1 { status="CONFLICTING_OCR" }
    else if let p=p,let t=t {
        let outstanding=t.mills-p.mills
        expected=outstanding
        let sum=wagers.reduce(0){$0+$1.0.mills}
        if outstanding < 0 {status="INCONSISTENT_TOTAL_BELOW_POT"}
        else if outstanding == 0 && wagers.count == 0 && extraneous.isEmpty {status="BALANCED_NO_WAGERS"}
        else if outstanding > 0 && !wagers.isEmpty && sum == outstanding && extraneous.isEmpty {status="BALANCED_WAGERS"}
        else {status="UNRESOLVED_ARITHMETIC"}
    }
    return NumericSnapshot(hand:hand,frame:frame,sourceFingerprint:fingerprint,pot:p,total:t,wagers:wagers,extraneous:extraneous,status:status,expectedOutstanding:expected)
}
func loadOCR(_ root:URL, _ n:Int) throws -> [String:Any] {
    let u=root.appendingPathComponent(String(format:"local_ocr/%06d.json",n))
    guard let j=try jsonFile(u) as? [String:Any] else {throw NSError(domain:"OCR_BAD",code:n)}
    return j
}
func report(_ r:NumericSnapshot) {
    print("frame=\(r.frame) hand=\(r.hand) pot=\(r.pot?.display ?? "UNKNOWN") total=\(r.total?.display ?? "UNKNOWN") outstanding=\(r.expectedOutstanding.map(formatBB) ?? "UNKNOWN") reconciled=\(r.status) wagers=\(r.wagers.map {"\($0.0.display)@\($0.1.visibleLabel)"}.joined(separator:",")) extra=\(r.extraneous.map{$0.display}.joined(separator:","))")
}
func sample(_ r:URL,_ n:Int,_ expected:String,_ amounts:[Int]) throws {
    guard let a=extractSnapshot(try loadOCR(r,n),knownNames:[]) else {throw NSError(domain:"MISSING_SNAPSHOT",code:n)}
    report(a)
    guard a.status == expected && a.wagers.map({$0.0.mills}).sorted() == amounts.sorted() else {
        throw NSError(domain:"RECONCILIATION_MISMATCH",code:n)
    }
}
func scan(_ root:URL,_ out:URL) throws {
    guard let frames=try jsonFile(root.appendingPathComponent("frames.json")) as? [[String:Any]] else {throw NSError(domain:"MISSING_FRAMES",code:1)}
    // Hand-scoped roster metadata; future rosters cannot be used on earlier frames.
    let rosters = allNumericRosters(root,through:frames.count)
    var priorSeatsByHand = [String:[String:(Double,Double)]]()
    var unknownAnchorsByHand = [String:[(Double,Double)]]()
    var rosterLoaded = Set<String>()
    var history = [[String:Any]]()
    var counts=[String:Int]()
    for (idx,frame) in frames.enumerated() {
        let n=idx+1
        guard frame["id"] as? Int == n else{throw NSError(domain:"FRAME_SEQUENCE",code:n)}
        let doc=try loadOCR(root,n)
        guard doc["frame"] as? Int == n else{throw NSError(domain:"OCR_SEQUENCE",code:n)}
        let lines=parseLines(doc)
        let hand=lines.compactMap{captureMatch(rxHand,$0.text)}.first
        if let hand=hand, let r=rosters.first(where:{($0["hand"] as? String)==hand && ($0["eligibleFromFrame"] as? Int ?? $0["rosterFrame"] as? Int ?? Int.max)<n}),!rosterLoaded.contains(hand) {
            let rosterFrame=r["rosterFrame"] as? Int ?? 0
            if rosterFrame>=1 && rosterFrame<n,let names=r["clockwiseRing"] as? [String] {
                let rdoc=try loadOCR(root,rosterFrame)
                var known=[String:(Double,Double)]()
                for line in parseLines(rdoc) where names.contains(line.text) && line.confidence >= 0.8 {
                    if known[line.text] == nil { known[line.text]=(line.x,line.y) }
                }
                priorSeatsByHand[hand]=known
                unknownAnchorsByHand[hand]=unknownNumericSeatAnchors(r)
                rosterLoaded.insert(hand)
            }
        }
        if let r=extractSnapshot(doc, knownNames:hand.flatMap{priorSeatsByHand[$0].map { Array($0.keys) }} ?? [],pastSeats:hand.flatMap{priorSeatsByHand[$0]} ?? [:]) {
            counts[r.status,default:0]+=1
            if r.pot != nil || r.total != nil {
                history.append(r.jsonValue(unknownSeatAnchors:hand.flatMap{unknownAnchorsByHand[$0]} ?? []))
            }
        }
    }
    let object:[String:Any]=["recording":root.lastPathComponent,"total_frames":frames.count,"numeric_snapshots":history,"status_counts":counts,"authoritative_actions_created":0,"network_calls":0]
    let data=try JSONSerialization.data(withJSONObject:object,options:[.sortedKeys,.prettyPrinted])
    try data.write(to:out,options:.atomic)
    print("NUMERIC_SCAN_PASS frames=\(frames.count) status=\(counts.sorted{$0.key<$1.key}.map{"\($0.key):\($0.value)"}.joined(separator:",")) output=\(out.path)")
}

// Read-only, frame-proven partial seat roster recovery for numeric evidence.
// A truncated nameplate is a physical seat, never a verified player name.
func recoveredPartialNumericRosters(_ root:URL, through:Int) -> [[String:Any]] {
    let buttonsURL = root.appendingPathComponent("observed_button_from_blinds.json")
    let cardsURL = root.appendingPathComponent("observed_card_back_pairs.json")
    let boardURL = root.appendingPathComponent("local_board_observations.json")
    guard let buttons = try? jsonFile(buttonsURL) as? [[String:Any]],
          let cards = try? jsonFile(cardsURL) as? [[String:Any]],
          let boards = try? jsonFile(boardURL) as? [[String:Any]],
          cards.count == boards.count else {return []}

    let unknown = "UNRESOLVED_PHYSICAL_SEAT"
    let pattern = try! NSRegularExpression(pattern:"^[A-Za-z0-9_]{3,31}(?:\\.\\.\\.)?$")
    func candidateName(_ name:String) -> Bool {
        guard pattern.firstMatch(in:name,range:NSRange(name.startIndex..<name.endIndex,in:name)) != nil,
              name.rangeOfCharacter(from:.letters) != nil,
              !isInterfaceLabel(name) else {return false}
        return true
    }
    func pairAt(_ pair:[String:Any],_ line:OCRLine) -> Bool {
        guard let x=pair["x"] as? Double,let y=pair["y"] as? Double else {return false}
        return abs(x-line.x)<0.030 && (1-line.y)-y > 0.030 && (1-line.y)-y < 0.085
    }
    func pairs(_ row:[String:Any]) -> [[String:Any]] {
        (row["pairs"] as? [[String:Any]] ?? []) +
        (row["faceUpPairs"] as? [[String:Any]] ?? [])
    }
    func sameCycle(_ a:[String],_ b:[String]) -> Bool {
        guard a.count == b.count else {return false}
        return a.indices.contains { i in Array(a[i...])+Array(a[..<i]) == b }
    }
    func sourceMatches(_ n:Int,_ doc:[String:Any],_ hand:String) -> Bool {
        guard n>=1,n<=cards.count,
              let fp=doc["sourceFingerprint"] as? String,
              doc["frame"] as? Int == n,
              cards[n-1]["frame"] as? Int == n,
              boards[n-1]["frame"] as? Int == n,
              cards[n-1]["sourceFingerprint"] as? String == fp,
              boards[n-1]["sourceFingerprint"] as? String == fp,
              cards[n-1]["hand"] as? String == hand,
              boards[n-1]["hand"] as? String == hand,
              boards[n-1]["visibleBoardCount"] as? Int == 0
        else {return false}
        let ids=parseLines(doc).compactMap {captureMatch(rxHand,$0.text)}
        return ids.count==1 && ids[0]==hand
    }

    var recovered = [[String:Any]]()
    for proof in buttons {
        guard let hand=proof["hand"] as? String,
              let f=proof["firstFrame"] as? Int,
              let c=proof["confirmedFrame"] as? Int,
              c==f+1,c<=through,c<=cards.count,
              let blindRing=proof["clockwiseRing"] as? [String],
              let dealer=proof["dealer"] as? String,
              let sb=proof["smallBlind"] as? String,
              let bb=proof["bigBlind"] as? String,
              let firstDoc=try? loadOCR(root,f),
              let confirmDoc=try? loadOCR(root,c),
              sourceMatches(f,firstDoc,hand),sourceMatches(c,confirmDoc,hand),
              firstDoc["sourceFingerprint"] as? String == proof["firstFingerprint"] as? String,
              confirmDoc["sourceFingerprint"] as? String == proof["confirmedFingerprint"] as? String
        else {continue}

        for n in stride(from:c,through:max(2,f-18),by:-1) {
            guard n>=2,n<=through,
                  let prior=try? loadOCR(root,n-1),
                  let current=try? loadOCR(root,n),
                  sourceMatches(n-1,prior,hand),
                  sourceMatches(n,current,hand)
            else {continue}
            let older=pairs(cards[n-2]), newer=pairs(cards[n-1])
            guard older.count==newer.count,(3...10).contains(older.count) else {continue}
            let nowLines=parseLines(current)
            var usedBefore=Set<Int>(),usedNow=Set<Int>()
            var seats=[(name:String,x:Double,y:Double)]()
            var truncatedCount=0
            for line in nowLines where line.confidence>=0.8 && candidateName(line.text) {
                let stacks=nowLines.filter {
                    $0.confidence>=0.8 && captureMatch(rxAmount,$0.text) != nil &&
                    abs($0.x-line.x)<0.028 && line.y-$0.y>0.025 && line.y-$0.y<0.058
                }
                guard stacks.count==1 else {continue}
                // The previous nameplate may be an action overlay.
                // Prove the seat with physical cards in both frames.
                let beforeMatches=older.indices.filter {pairAt(older[$0],line)}
                let nowMatches=newer.indices.filter {pairAt(newer[$0],line)}
                guard beforeMatches.count==1,nowMatches.count==1,
                      !usedBefore.contains(beforeMatches[0]),
                      !usedNow.contains(nowMatches[0]),
                      let px=older[beforeMatches[0]]["x"] as? Double,
                      let py=older[beforeMatches[0]]["y"] as? Double,
                      let qx=newer[nowMatches[0]]["x"] as? Double,
                      let qy=newer[nowMatches[0]]["y"] as? Double,
                      abs(px-qx)<0.018,abs(py-qy)<0.018
                else {continue}
                usedBefore.insert(beforeMatches[0]);usedNow.insert(nowMatches[0])
                let truncated=line.text.hasSuffix("...")
                if truncated {truncatedCount+=1}
                seats.append((truncated ? unknown : line.text,line.x,line.y))
            }
            guard seats.count==older.count,
                  usedBefore.count==older.count,
                  usedNow.count==newer.count,
                  truncatedCount<=1,
                  Set(seats.map{$0.name}).count==seats.count
            else {continue}
            let centerX=(seats.map{$0.x}.min()!+seats.map{$0.x}.max()!)/2
            let centerY=(seats.map{$0.y}.min()!+seats.map{$0.y}.max()!)/2
            let ring=seats.sorted {
                atan2($0.y-centerY,$0.x-centerX)>atan2($1.y-centerY,$1.x-centerX)
            }.map{$0.name}
            let knownRing=ring.filter{blindRing.contains($0)}
            guard Set(blindRing).isSubset(of:Set(ring)),
                  sameCycle(knownRing,blindRing),
                  let d=ring.firstIndex(of:dealer),
                  ring[(d+1)%ring.count]==sb,
                  ring[(d+2)%ring.count]==bb
            else {continue}
            recovered.append([
                "hand":hand,"rosterFrame":n,"priorFrame":n-1,
                "eligibleFromFrame":c,"clockwiseRing":ring,
                "dealer":dealer,"smallBlind":sb,"bigBlind":bb,
                "unresolvedPhysicalSeats":truncatedCount,
                "unresolvedSeatAnchors":seats.filter{$0.name == unknown}.map {
                    ["x":$0.x,"y":$0.y]
                },
                "sourceFingerprints":[prior["sourceFingerprint"]!,current["sourceFingerprint"]!]
            ])
            break
        }
    }
    return recovered
}
func unknownNumericSeatAnchors(_ roster:[String:Any]) -> [(Double,Double)] {
    let entries=roster["unresolvedSeatAnchors"] as? [[String:Any]] ?? []
    return entries.compactMap { item in
        guard let x=item["x"] as? Double,let y=item["y"] as? Double,
              x>=0,x<=1,y>=0,y<=1 else {return nil}
        return (x,y)
    }
}

// Seated players can be visible in the later nameplate/position ring
// without having had cards in the initial dealt-in ring. No extra
// seated player is promoted to a dealt-in participant. A case-only OCR
// variant is accepted only if it occupies the *same physical seat*.
func corroboratedSeatedOnlyExtras(
    dealtRing: [String], seatedRing: [String],
    dealtPositions: [String:(Double,Double)],
    earlierCards: [[String:Any]], currentCards: [[String:Any]],
    rosterOCR: [String:Any], blindFirstOCR: [String:Any],
    blindConfirmedOCR: [String:Any]
) -> Bool {
    guard dealtRing.count >= 3, seatedRing.count > dealtRing.count,
          dealtRing.count <= 10, seatedRing.count <= 10,
          dealtRing.allSatisfy({!$0.hasPrefix("UNRESOLVED_")}),
          seatedRing.allSatisfy({!isInterfaceLabel($0)})
    else {return false}

    func normalized(_ s:String) -> String {s.lowercased()}
    let dealtKeys=dealtRing.map(normalized)
    let seatedKeys=seatedRing.map(normalized)
    guard Set(dealtKeys).count==dealtKeys.count,
          Set(seatedKeys).count==seatedKeys.count,
          Set(dealtKeys).isSubset(of:Set(seatedKeys)) else {return false}

    let dealtSet=Set(dealtKeys)
    let projected=seatedKeys.filter{dealtSet.contains($0)}
    guard projected.count==dealtKeys.count,
          dealtKeys.indices.contains(where:{i in
              Array(dealtKeys[i...])+Array(dealtKeys[..<i]) == projected
          }) else {return false}

    let earlyLines=parseLines(rosterOCR)
    let laterLines=parseLines(blindConfirmedOCR)
    let firstLines=parseLines(blindFirstOCR)

    func nameplate(_ name:String,_ lines:[OCRLine]) -> OCRLine? {
        let exact=lines.filter{$0.text==name && $0.confidence>=0.8}
        return exact.count==1 ? exact[0] : nil
    }
    func stableLabel(_ a:OCRLine,_ b:OCRLine) -> Bool {
        hypot(a.x-b.x,a.y-b.y)<0.012
    }
    func cardsAt(_ x:Double,_ y:Double,_ cards:[[String:Any]]) -> Bool {
        cards.contains{card in
            guard let cx=card["x"] as? Double,
                  let cy=card["y"] as? Double else{return false}
            return abs(cx-x)<0.030 && (1-y)-cy>0.030 && (1-y)-cy<0.085
        }
    }
    // Every already-dealt-in name must map to the same physical seat,
    // even when capitalization changed between OCR frames.
    for early in dealtRing {
        guard let point=dealtPositions[early],
              let laterName=seatedRing.first(where:{normalized($0)==normalized(early)}),
              let earlyLabel=nameplate(early,earlyLines),
              let laterLabel=nameplate(laterName,laterLines),
              stableLabel(earlyLabel,laterLabel),
              hypot(earlyLabel.x-point.0,earlyLabel.y-point.1)<0.012
        else {return false}
    }
    // Additional seated names are not evidence of being dealt in.
    // They must be stable in both blind frames and have *no* pair
    // at that seat in either early hand frame.
    var extraPositions=[(Double,Double)]()
    for late in seatedRing where !dealtSet.contains(normalized(late)) {
        guard let a=nameplate(late,firstLines),
              let b=nameplate(late,laterLines),
              stableLabel(a,b),
              !cardsAt(b.x,b.y,earlierCards),
              !cardsAt(b.x,b.y,currentCards),
              !extraPositions.contains(where:{hypot($0.0-b.x,$0.1-b.y)<0.025})
        else {return false}
        extraPositions.append((b.x,b.y))
    }
    return !extraPositions.isEmpty
}

// A Recorder roster is observational until its original frames and a
// same-hand two-frame blind proof establish a causal eligibility point.
// Never carry a player's name across hands or grant it before that point.
func certifiedImportedNumericRoster(_ root:URL, _ row:[String:Any], through:Int) -> [String:Any]? {
    guard let hand=row["hand"] as? String,
          let ring=row["clockwiseRing"] as? [String],
          let prior=row["priorFrame"] as? Int,
          let frame=row["rosterFrame"] as? Int,
          frame==prior+1, prior>=1, frame<=through,
          (3...10).contains(ring.count),Set(ring).count==ring.count,
          let fingerprint=row["sourceFingerprints"] as? [String],fingerprint.count==2,
          let dealer=row["dealer"] as? String,
          let sb=row["smallBlind"] as? String,
          let bb=row["bigBlind"] as? String,
          let btn=try? jsonFile(root.appendingPathComponent("observed_button_from_blinds.json")) as? [[String:Any]],
          let boards=try? jsonFile(root.appendingPathComponent("local_board_observations.json")) as? [[String:Any]],
          let cards=try? jsonFile(root.appendingPathComponent("observed_card_back_pairs.json")) as? [[String:Any]],
          boards.count==cards.count,frame<=cards.count,
          let older=try? loadOCR(root,prior),
          let now=try? loadOCR(root,frame)
    else {return nil}

    let manifest=(try? jsonFile(root.appendingPathComponent("frames.json")) as? [[String:Any]]) ?? []
    func sameHand(_ n:Int,_ doc:[String:Any]) -> Bool {
        guard n>=1,n<=boards.count,n<=manifest.count,
              let fp=doc["sourceFingerprint"] as? String,
              doc["frame"] as? Int == n,
              boards[n-1]["frame"] as? Int == n,
              cards[n-1]["frame"] as? Int == n,
              boards[n-1]["sourceFingerprint"] as? String == fp,
              cards[n-1]["sourceFingerprint"] as? String == fp,
              boards[n-1]["hand"] as? String == hand,
              cards[n-1]["hand"] as? String == hand,
              boards[n-1]["visibleBoardCount"] as? Int == 0
        else {return false}
        let ids=parseLines(doc).compactMap{captureMatch(rxHand,$0.text)}
        guard ids.count==1,ids[0]==hand,
              manifest[n-1]["id"] as? Int == n,
              let relative=manifest[n-1]["file"] as? String,
              !relative.hasPrefix("/"),!relative.contains("..")
        else {return false}
        #if canImport(CryptoKit)
        guard let bytes=try? Data(contentsOf:root.appendingPathComponent(relative)) else {return false}
        let digest=SHA256.hash(data:bytes).map{String(format:"%02x",$0)}.joined()
        guard fp=="sha256:"+digest else {return false}
        #endif
        return true
    }
    guard sameHand(prior,older),sameHand(frame,now),
          fingerprint[0] != fingerprint[1],
          older["sourceFingerprint"] as? String == fingerprint[0],
          now["sourceFingerprint"] as? String == fingerprint[1]
    else {return nil}

    // Physical card-back/face-up pairs are required for every seat.
    func pairs(_ n:Int) -> [[String:Any]] {
        (cards[n-1]["pairs"] as? [[String:Any]] ?? []) +
        (cards[n-1]["faceUpPairs"] as? [[String:Any]] ?? [])
    }
    let p=pairs(prior),q=pairs(frame)
    guard p.count==q.count,p.count==ring.count else {return nil}
    var points=[String:(Double,Double)]()
    let nowLines=parseLines(now)
    let unknowns=ring.filter{$0.hasPrefix("UNRESOLVED_")}
    let anchors=unknownNumericSeatAnchors(row)
    guard unknowns.count<=1,unknowns.count==anchors.count else {return nil}
    for name in ring {
        if isInterfaceLabel(name) {return nil}
        let x:Double,y:Double
        if name.hasPrefix("UNRESOLVED_") {
            guard let point=anchors.first else {return nil}
            x=point.0;y=point.1
        } else {
            let lines=nowLines.filter{$0.text==name && $0.confidence>=0.8}
            guard lines.count==1 else {return nil}
            x=lines[0].x;y=lines[0].y
            let stacks=nowLines.filter {
                $0.confidence>=0.8 && captureMatch(rxAmount,$0.text) != nil &&
                abs($0.x-x)<0.034 && y-$0.y>0.022 && y-$0.y<0.072
            }
            guard stacks.count==1 else {return nil}
        }
        for cardList in [p,q] {
            let found=cardList.filter { card in
                guard let px=card["x"] as? Double,let py=card["y"] as? Double else {return false}
                return abs(px-x)<0.030 && (1-y)-py>0.030 && (1-y)-py<0.085
            }
            guard found.count==1 else {return nil}
        }
        points[name]=(x,y)
    }
    // A different seat may not claim the same physical card.
    for cardList in [p,q] {
        var claimed=Set<Int>()
        for name in ring {
            let point=points[name]!
            let matches=cardList.indices.filter { i in
                guard let x=cardList[i]["x"] as? Double,
                      let y=cardList[i]["y"] as? Double else {return false}
                return abs(x-point.0)<0.030 && (1-point.1)-y>0.030 && (1-point.1)-y<0.085
            }
            guard matches.count==1,claimed.insert(matches[0]).inserted else {return nil}
        }
        guard claimed.count==ring.count else {return nil}
    }
    func sameCycle(_ a:[String],_ b:[String]) -> Bool {
        guard a.count==b.count else {return false}
        return a.indices.contains{i in Array(a[i...])+Array(a[..<i]) == b}
    }
    let proofs=btn.filter { b in
        b["hand"] as? String == hand &&
        b["dealer"] as? String == dealer &&
        b["smallBlind"] as? String == sb &&
        b["bigBlind"] as? String == bb
    }
    guard proofs.count==1,let blind=proofs.first,
          let f=blind["firstFrame"] as? Int,
          let c=blind["confirmedFrame"] as? Int,
          c==f+1,c<=through,
          let fdoc=try? loadOCR(root,f),let cdoc=try? loadOCR(root,c),
          sameHand(f,fdoc),sameHand(c,cdoc),
          fdoc["sourceFingerprint"] as? String == blind["firstFingerprint"] as? String,
          cdoc["sourceFingerprint"] as? String == blind["confirmedFingerprint"] as? String,
          let blindRing=blind["clockwiseRing"] as? [String],
          (
              (Set(blindRing).isSubset(of:Set(ring)) &&
               sameCycle(ring.filter{blindRing.contains($0)},blindRing)) ||
              corroboratedSeatedOnlyExtras(
                  dealtRing:ring, seatedRing:blindRing,
                  dealtPositions:points, earlierCards:p, currentCards:q,
                  rosterOCR:now, blindFirstOCR:fdoc, blindConfirmedOCR:cdoc
              )
          ),
          let index=ring.firstIndex(of:dealer),
          ring[(index+1)%ring.count]==sb,
          ring[(index+2)%ring.count]==bb
    else {return nil}

    var certified=row
    certified["eligibleFromFrame"]=max(c,frame)
    certified["unresolvedPhysicalSeats"]=unknowns.count
    certified["unresolvedSeatAnchors"]=anchors.map{["x":$0.0,"y":$0.1]}
    certified["identityProof"]="BLIND_AND_ORIGINAL_CARD_FRAMES"
    return certified
}

func allNumericRosters(_ root:URL, through:Int) -> [[String:Any]] {
    let file=root.appendingPathComponent("observed_verified_dealt_in_rosters.json")
    let untrusted=(try? jsonFile(file) as? [[String:Any]]) ?? []
    var existing=untrusted.compactMap{certifiedImportedNumericRoster(root,$0,through:through)}
    for candidate in recoveredPartialNumericRosters(root,through:through) {
        guard let hand=candidate["hand"] as? String else {continue}
        if let i=existing.firstIndex(where:{$0["hand"] as? String == hand}) {
            // A historical partial-roster sidecar may omit the unknown
            // seat's geometry. Enrich only when the ring and frame agree.
            if let priorRing=existing[i]["clockwiseRing"] as? [String],
               let newRing=candidate["clockwiseRing"] as? [String],
               priorRing.count==newRing.count,
               zip(priorRing,newRing).allSatisfy({ pair in
                   pair.0==pair.1 || (pair.0.hasPrefix("UNRESOLVED_") && pair.1.hasPrefix("UNRESOLVED_"))
               }),
               existing[i]["rosterFrame"] as? Int == candidate["rosterFrame"] as? Int {
                existing[i]["unresolvedSeatAnchors"] = candidate["unresolvedSeatAnchors"]
            }
        } else {
            existing.append(candidate)
        }
    }
    return existing
}

// Read-only incremental numeric projection.
// Recorder remains the sole writer of current_hand.txt and actions.
struct NumericFollowCursor {
    let root: URL
    var through: Int = 0
    var snapshots = [[String:Any]]()
    var counts = [String:Int]()
    var priorSeatsByHand = [String:[String:(Double,Double)]]()
    var unknownAnchorsByHand = [String:[(Double,Double)]]()
    var rosterLoaded = Set<String>()

    mutating func consume(frames: [[String:Any]], through end: Int) throws {
        guard end >= through && end <= frames.count else {
            throw NSError(domain:"NUMERIC_CURSOR_INVALID",code:end)
        }
        guard end > through else { return }

        let rosters = allNumericRosters(root,through:end)

        for n in (through+1)...end {
            let frame = frames[n-1]
            guard frame["id"] as? Int == n else {
                throw NSError(domain:"NUMERIC_FRAME_ID",code:n)
            }

            let doc = try loadOCR(root,n)
            guard doc["frame"] as? Int == n,
                  let fingerprint = doc["sourceFingerprint"] as? String,
                  fingerprint.hasPrefix("sha256:") else {
                throw NSError(domain:"NUMERIC_OCR_IDENTITY",code:n)
            }

            #if canImport(CryptoKit)
            guard let relative = frame["file"] as? String,
                  !relative.hasPrefix("/"),
                  !relative.contains("..") else {
                throw NSError(domain:"NUMERIC_IMAGE_PATH",code:n)
            }

            let bytes = try Data(
                contentsOf:root.appendingPathComponent(relative)
            )
            let digest = SHA256.hash(data:bytes).map {
                String(format:"%02x",$0)
            }.joined()

            guard fingerprint == "sha256:"+digest else {
                throw NSError(domain:"NUMERIC_IMAGE_FINGERPRINT",code:n)
            }
            #endif

            let lines = parseLines(doc)
            let hands = lines.compactMap {
                captureMatch(rxHand,$0.text)
            }
            let hand = hands.count == 1 ? hands[0] : nil

            if let hand = hand,
               let roster = rosters.first(where:{
                   ($0["hand"] as? String) == hand &&
                   ($0["eligibleFromFrame"] as? Int ?? $0["rosterFrame"] as? Int ?? Int.max) < n
               }), !rosterLoaded.contains(hand) {

                let rosterFrame = roster["rosterFrame"] as? Int ?? 0

                if rosterFrame >= 1 && rosterFrame < n,
                   let names = roster["clockwiseRing"] as? [String] {

                    let rdoc = try loadOCR(root,rosterFrame)
                    var known = [String:(Double,Double)]()

                    for line in parseLines(rdoc)
                        where names.contains(line.text) &&
                              line.confidence >= 0.8 {
                        if known[line.text] == nil {
                            known[line.text] = (line.x,line.y)
                        }
                    }

                    priorSeatsByHand[hand] = known
                    unknownAnchorsByHand[hand] = unknownNumericSeatAnchors(roster)
                    rosterLoaded.insert(hand)
                }
            }

            if let observation = extractSnapshot(
                doc,
                knownNames:hand.flatMap {
                    priorSeatsByHand[$0].map { Array($0.keys) }
                } ?? [],
                pastSeats:hand.flatMap {
                    priorSeatsByHand[$0]
                } ?? [:]
            ) {
                guard observation.frame == n &&
                      observation.sourceFingerprint == fingerprint else {
                    throw NSError(domain:"NUMERIC_FRAME_OWNERSHIP",code:n)
                }

                counts[observation.status,default:0] += 1

                if observation.pot != nil || observation.total != nil {
                    snapshots.append(observation.jsonValue(unknownSeatAnchors:hand.flatMap{unknownAnchorsByHand[$0]} ?? []))
                }
            }

            through = n
        }
    }

    func data() throws -> Data {
        let object:[String:Any] = [
            "recording":root.lastPathComponent,
            "total_frames":through,
            "numeric_snapshots":snapshots,
            "status_counts":counts,
            "authoritative_actions_created":0,
            "network_calls":0
        ]
        return try JSONSerialization.data(
            withJSONObject:object,
            options:[.sortedKeys,.prettyPrinted]
        )
    }
}

func numericFollowerReplayTest(_ root: URL, _ output: URL) throws {
    guard let frames = try jsonFile(
        root.appendingPathComponent("frames.json")
    ) as? [[String:Any]] else {
        throw NSError(domain:"MISSING_FRAMES",code:1)
    }

    var cursor = NumericFollowCursor(root:root)
    let size = frames.count

    let boundaries = [
        0,1,2,3,17,18,44,73,100,160,200,
        233,234,235,236,237,238,299,319,size
    ].filter { $0 <= size }

    for edge in boundaries.sorted() {
        try cursor.consume(frames:frames,through:edge)
    }

    try cursor.consume(frames:frames,through:size)
    try cursor.data().write(to:output,options:.atomic)

    print(
        "NUMERIC_INCREMENTAL_REPLAY_PASS frames=\(size) " +
        "through=\(cursor.through) actions=0"
    )
}

func followNumericSession(
    _ root: URL, _ output: URL, pollMilliseconds: Int
) throws {
    guard pollMilliseconds >= 100 && pollMilliseconds <= 5000 else {
        throw NSError(domain:"FOLLOW_CADENCE",code:pollMilliseconds)
    }

    // The follower cannot overwrite the authoritative hand history.
    guard output.lastPathComponent ==
              "observed_numeric_snapshots.json",
          output.deletingLastPathComponent()
              .standardizedFileURL.path ==
              root.standardizedFileURL.path else {
        throw NSError(domain:"NUMERIC_OUTPUT_OWNERSHIP",code:1)
    }

    let statusURL = root.appendingPathComponent("status.json")
    let framesURL = root.appendingPathComponent("frames.json")
    var cursor = NumericFollowCursor(root:root)
    var lastObserved = 0
    var missingStart = Date()

    while true {
        if let status = try? jsonFile(statusURL) as? [String:Any],
           let analyzed = status["analyzed"] as? Int,
           let frames = try? jsonFile(framesURL) as? [[String:Any]],
           analyzed >= cursor.through &&
           analyzed <= frames.count {

            missingStart = Date()

            if analyzed > cursor.through {
                try cursor.consume(frames:frames,through:analyzed)
                try cursor.data().write(to:output,options:.atomic)

                lastObserved = analyzed

                print(
                    "NUMERIC_FOLLOW_PROGRESS through=\(analyzed) " +
                    "records=\(cursor.snapshots.count)"
                )
            }

            let stopped = status["stopped"] as? Bool ?? false

            if stopped && lastObserved == analyzed {
                if !FileManager.default.fileExists(
                    atPath:output.path
                ) {
                    try cursor.data().write(
                        to:output,options:.atomic
                    )
                }

                print(
                    "NUMERIC_FOLLOW_PASS frames=\(cursor.through) actions=0"
                )
                return
            }

        } else if Date().timeIntervalSince(missingStart) > 30 {
            throw NSError(domain:"NUMERIC_SOURCE_STALE",code:0)
        }

        Thread.sleep(
            forTimeInterval:Double(pollMilliseconds)/1000.0
        )
    }
}

@main struct QuantitativeReadOnly {
    static func main() throws {
        let args=CommandLine.arguments
        if args.count==4 && args[1]=="--native-roster-proof" {
            guard let n=Int(args[3]) else {throw NSError(domain:"BAD_FRAME",code:1)}
            let items=allNumericRosters(URL(fileURLWithPath:args[2]),through:n)
            let data=try JSONSerialization.data(withJSONObject:items,options:[.prettyPrinted,.sortedKeys])
            print(String(decoding:data,as:UTF8.self))
        } else if args.count==4 && args[1]=="--check" {
            let a=URL(fileURLWithPath:args[2]),b=URL(fileURLWithPath:args[3])
            try sample(a,314,"BALANCED_WAGERS",[3330,8160])
            try sample(b,315,"BALANCED_WAGERS",[1000,500])
            // Pot chip decoration should not be counted as an opponent wager.
            try sample(a,334,"UNRESOLVED_ARITHMETIC",[])
            var changed=try loadOCR(a,314)
            if var cap=changed["capture"] as? [String:Any],var lines=cap["lines"] as? [[String:Any]],
               let idx=lines.firstIndex(where:{($0["text"] as? String)=="8.16 BB"}) {
                lines[idx]["text"]="8.17 BB"
                cap["lines"]=lines
                changed["capture"]=cap
            } else {throw NSError(domain:"ORIGINAL_WAGER_NOT_FOUND",code:314)}
            guard extractSnapshot(changed,knownNames:[])?.status == "UNRESOLVED_ARITHMETIC" else {
                throw NSError(domain:"BAD_WAGER_NOT_REJECTED",code:314)
            }
            let refA = extractSnapshot(try loadOCR(a,314),knownNames:[])
            let refB = extractSnapshot(try loadOCR(b,315),knownNames:[])
            guard let pa=refA,let pb=refB,
                  pa.wagers.count == 2,pb.wagers.count == 2,
                  pa.wagers.allSatisfy({ !$0.1.visibleLabel.contains("RAISE") }),
                  pb.wagers.allSatisfy({ !$0.1.visibleLabel.contains("Post") }),
                  (pa.wagers+pb.wagers).allSatisfy({ $0.1.knownName == nil })
            else {throw NSError(domain:"UNVERIFIED_UI_LABEL_AS_PLAYER",code:314)}
            let forged = extractSnapshot(
                try loadOCR(a,314),knownNames:["RAISE"],
                pastSeats:["RAISE":(0.520,0.156)])
            let forgedBB = extractSnapshot(
                try loadOCR(b,315),knownNames:["Post BB","Post SB"],
                pastSeats:["Post BB":(0.519,0.155),"Post SB":(0.721,0.231)])
            guard forged?.wagers.count == 2,forgedBB?.wagers.count == 2,
                  forged!.wagers.allSatisfy({ $0.1.knownName == nil }),
                  forgedBB!.wagers.allSatisfy({ $0.1.knownName == nil })
            else {throw NSError(domain:"FORGED_OVERLAY_IDENTITY_ACCEPTED",code:315)}
            print("QUANTITATIVE_ANCHOR_PASS arithmetic=2/2 unresolved_pot_overlay=1 bad_wager_gate=YES identity_overlays_blocked=YES fabricated_actions=0")
        } else if args.count==4 && args[1]=="--scan" {
            try scan(URL(fileURLWithPath:args[2]),URL(fileURLWithPath:args[3]))
        } else if args.count==4 && args[1]=="--incremental-test" {
            try numericFollowerReplayTest(URL(fileURLWithPath:args[2]),URL(fileURLWithPath:args[3]))
        } else if args.count==5 && args[1]=="--follow" {
            guard let ms=Int(args[4]) else {
                throw NSError(domain:"BAD_MS",code:4)
            }
            try followNumericSession(
                URL(fileURLWithPath:args[2]),
                URL(fileURLWithPath:args[3]),
                pollMilliseconds:ms
            )
        } else {
            print("Usage: --check <353> <354> | --scan <root> <out> | --incremental-test <root> <out> | --follow <root> <out> <poll_ms>")
            throw NSError(domain:"ARGS",code:1)
        }
    }
}
