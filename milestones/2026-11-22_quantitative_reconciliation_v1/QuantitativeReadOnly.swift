import Foundation

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
    func jsonValue() -> [String: Any] {
        var d: [String:Any] = ["hand":hand,"frame":frame,"source_fingerprint":sourceFingerprint,"status":status,"not_authoritative":true]
        if let pot = pot { d["pot_bb"] = pot.display }
        if let total = total { d["total_bb"] = total.display }
        if let e = expectedOutstanding { d["expected_outstanding_bb"] = formatBB(e) }
        d["wagers"] = wagers.map { amount,seat in
            var w:[String:Any] = ["amount_bb":amount.display,"source_text":amount.line.text,"x":amount.line.x,"y":amount.line.y,"seat_label":seat.visibleLabel,"identity_status":seat.knownName == nil ? "UNRESOLVED" : "EARLIER_FRAME_VERIFIED"]
            if let name = seat.knownName { w["player"] = name }
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
        let name = knownNames.contains(label.text) ? label.text : nil
        anchors.append(SeatAnchor(visibleLabel:label.text,x:label.x,y:label.y,knownName:name))
    }
    // Past seats are valid only when a roster was established on a *previous* frame.
    for name in pastSeats.keys.sorted() {
        guard let point=pastSeats[name] else {continue}
        anchors.removeAll { a in
            a.knownName == nil && hypot(a.x-point.0,a.y-point.1)<0.018
        }
        if !anchors.contains(where:{$0.knownName == name}) {
            anchors.append(SeatAnchor(visibleLabel:"EARLIER_ROSTER",x:point.0,y:point.1,knownName:name))
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
    var rosters = [[String:Any]]()
    let path=root.appendingPathComponent("observed_verified_dealt_in_rosters.json")
    if let array=try? jsonFile(path) as? [[String:Any]] {rosters=array}
    var priorSeatsByHand = [String:[String:(Double,Double)]]()
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
        if let hand=hand, let r=rosters.first(where:{($0["hand"] as? String)==hand && ($0["rosterFrame"] as? Int ?? Int.max)<n}),!rosterLoaded.contains(hand) {
            let rosterFrame=r["rosterFrame"] as? Int ?? 0
            if rosterFrame>=1 && rosterFrame<n,let names=r["clockwiseRing"] as? [String] {
                let rdoc=try loadOCR(root,rosterFrame)
                var known=[String:(Double,Double)]()
                for line in parseLines(rdoc) where names.contains(line.text) && line.confidence >= 0.8 {
                    if known[line.text] == nil { known[line.text]=(line.x,line.y) }
                }
                priorSeatsByHand[hand]=known
                rosterLoaded.insert(hand)
            }
        }
        if let r=extractSnapshot(doc, knownNames:hand.flatMap{priorSeatsByHand[$0].map { Array($0.keys) }} ?? [],pastSeats:hand.flatMap{priorSeatsByHand[$0]} ?? [:]) {
            counts[r.status,default:0]+=1
            if r.pot != nil || r.total != nil {
                history.append(r.jsonValue())
            }
        }
    }
    let object:[String:Any]=["recording":root.lastPathComponent,"total_frames":frames.count,"numeric_snapshots":history,"status_counts":counts,"authoritative_actions_created":0,"network_calls":0]
    let data=try JSONSerialization.data(withJSONObject:object,options:[.sortedKeys,.prettyPrinted])
    try data.write(to:out,options:.atomic)
    print("NUMERIC_SCAN_PASS frames=\(frames.count) status=\(counts.sorted{$0.key<$1.key}.map{"\($0.key):\($0.value)"}.joined(separator:",")) output=\(out.path)")
}
@main struct QuantitativeReadOnly {
    static func main() throws {
        let args=CommandLine.arguments
        if args.count==4 && args[1]=="--check" {
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
            print("QUANTITATIVE_ANCHOR_PASS arithmetic=2/2 unresolved_pot_overlay=1 bad_wager_gate=YES fabricated_actions=0")
        } else if args.count==4 && args[1]=="--scan" {
            try scan(URL(fileURLWithPath:args[2]),URL(fileURLWithPath:args[3]))
        } else {print("Usage: --check <353_root> <354_root> | --scan <run_root> <output.json>");throw NSError(domain:"ARGS",code:1)}
    }
}
