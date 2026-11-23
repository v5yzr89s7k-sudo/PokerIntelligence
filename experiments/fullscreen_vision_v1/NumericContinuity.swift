// Offline, read-only temporal projection of certified numeric snapshots.
// A visible numeric transition is NOT a poker action, bet size, or payout.
import Foundation

struct ContinuityError: Error, CustomStringConvertible {
    let description: String
    init(_ message:String) { description = message }
}
func required(_ ok:Bool,_ message:String) throws {
    if !ok { throw ContinuityError(message) }
}
func bb(_ text:Any?) -> Int? {
    guard let s=text as? String, !s.isEmpty,
          s.range(of:"^[0-9]{1,6}(?:\\.[0-9]{1,3})?$",options:.regularExpression) != nil else {return nil}
    let p=s.split(separator:".",omittingEmptySubsequences:false)
    guard let whole=Int(p[0]) else {return nil}
    var part=0
    if p.count==2 {
        guard let v=Int(p[1]) else {return nil}
        part=v*(p[1].count==1 ? 100 : (p[1].count==2 ? 10 : 1))
    }
    return whole*1000+part
}
func showBB(_ v:Int) -> String {
    let sign=v < 0 ? "-" : ""
    let a=abs(v),w=a/1000,r=a%1000
    if r==0 {return sign+String(w)}
    var fraction=String(format:"%03d",r)
    while fraction.hasSuffix("0") {fraction.removeLast()}
    return sign+String(w)+"."+fraction
}
struct Snapshot {
    let hand:String
    let frame:Int
    let fingerprint:String
    let pot:Int?
    let total:Int?
    let status:String
    let known:[String:Int]
    let unknownCount:Int
    let outstanding:Int
    let valid:Bool
}
func decode(_ row:[String:Any]) throws -> Snapshot {
    guard let hand=row["hand"] as? String,!hand.isEmpty,
          let n=row["frame"] as? Int,n>0,
          let fp=row["source_fingerprint"] as? String,
          fp.range(of:"^sha256:[0-9a-f]{64}$",options:.regularExpression) != nil,
          row["not_authoritative"] as? Bool == true,
          let status=row["status"] as? String,
          let wagers=row["wagers"] as? [[String:Any]],
          let extra=row["unassigned_numeric_labels"] as? [[String:Any]]
    else {throw ContinuityError("INVALID_NUMERIC_ROW")}
    let pot=bb(row["pot_bb"]),total=bb(row["total_bb"])
    var known=[String:Int](),unknown=0,totalWagers=0
    var duplicates=false
    for wager in wagers {
        guard let value=bb(wager["amount_bb"]),
              let state=wager["identity_status"] as? String,
              let label=wager["seat_label"] as? String else {
            throw ContinuityError("INVALID_WAGER_ROW")
        }
        totalWagers+=value
        if state == "EARLIER_FRAME_VERIFIED",
           let player=wager["player"] as? String,
           player==label,!player.isEmpty,!player.hasPrefix("UNRESOLVED_") {
            if known.updateValue(value,forKey:player) != nil {duplicates=true}
        } else { unknown+=1 }
    }
    let balanced:Bool
    if let p=pot,let t=total,t>=p,extra.isEmpty,!duplicates {
        balanced=(status == "BALANCED_WAGERS" && totalWagers>0 && t-p==totalWagers) ||
            (status == "BALANCED_NO_WAGERS" && totalWagers==0 && wagers.isEmpty && t==p)
    } else {balanced=false}
    return Snapshot(hand:hand,frame:n,fingerprint:fp,pot:pot,total:total,
                    status:status,known:known,unknownCount:unknown,
                    outstanding:totalWagers,valid:balanced)
}
func project(_ object:[String:Any]) throws -> [String:Any] {
    guard object["authoritative_actions_created"] as? Int == 0,
          object["network_calls"] as? Int == 0,
          let rows=object["numeric_snapshots"] as? [[String:Any]],
          let count=object["total_frames"] as? Int,count>=0
    else {throw ContinuityError("UNEXPECTED_NUMERIC_SCAN_CONTRACT")}
    var previous:Snapshot?=nil
    var observations=[[String:Any]](),withheld=[[String:Any]]()
    var verifiedPairCount=0
    for row in rows {
        let now=try decode(row)
        try required(now.frame<=count,"FRAME_OUTSIDE_RECORDING")
        if let before=previous {
            try required(now.frame>before.frame,"SNAPSHOTS_NOT_CHRONOLOGICAL")
            if now.hand==before.hand {
                let shared:[String:Any]=[
                    "hand":now.hand,"from_frame":before.frame,"to_frame":now.frame,
                    "from_fingerprint":before.fingerprint,"to_fingerprint":now.fingerprint,
                    "not_action":true]
                if now.frame != before.frame+1 {
                    withheld.append(["hand":now.hand,"from_frame":before.frame,"to_frame":now.frame,
                                     "reason":"MISSING_INTERMEDIATE_NUMERIC_FRAME"])
                } else if !now.valid || !before.valid {
                    withheld.append(["hand":now.hand,"from_frame":before.frame,"to_frame":now.frame,
                                     "reason":"UNBALANCED_OR_INCOMPLETE_NUMERIC_EVIDENCE"])
                } else if now.fingerprint==before.fingerprint &&
                          (now.pot != before.pot || now.total != before.total || now.outstanding != before.outstanding || now.known != before.known) {
                    withheld.append(["hand":now.hand,"from_frame":before.frame,"to_frame":now.frame,
                                     "reason":"IDENTICAL_IMAGE_WITH_CONFLICTING_NUMERIC_EVIDENCE"])
                } else {
                    verifiedPairCount+=1
                    func add(_ kind:String,_ more:[String:Any]) {
                        observations.append(shared.merging(["kind":kind].merging(more){_,n in n}){_,n in n})
                    }
                    // Never turn a changed numeric label into a bet/raise/call claim.
                    for name in before.known.keys.sorted() where now.known[name] != nil {
                        let old=before.known[name]!,new=now.known[name]!
                        if old != new {
                            add("VERIFIED_SEAT_WAGER_LABEL_CHANGED",[
                                "player":name,"before_bb":showBB(old),"after_bb":showBB(new),
                                "difference_bb":showBB(new-old)])
                        }
                    }
                    for name in now.known.keys.sorted() where before.known[name] == nil {
                        add("VERIFIED_SEAT_WAGER_LABEL_APPEARED",[
                            "player":name,"visible_bb":showBB(now.known[name]!)])
                    }
                    if let p=before.pot,let q=now.pot,let t=before.total,let u=now.total {
                        if q>p && t==u && before.outstanding-now.outstanding==q-p {
                            add("POT_AND_OUTSTANDING_CONSERVATION_OBSERVED",[
                                "pot_before_bb":showBB(p),"pot_after_bb":showBB(q),
                                "transferred_bb":showBB(q-p),"total_bb":showBB(u),
                                "player_attribution":"UNDETERMINED"])
                        }
                        if u != t {
                            add("VISIBLE_TOTAL_LABEL_CHANGED",[
                                "total_before_bb":showBB(t),"total_after_bb":showBB(u),
                                "difference_bb":showBB(u-t),"cause":"UNDETERMINED"])
                        }
                    }
                }
            }
        }
        previous=now
    }
    return ["schema":"PI_NUMERIC_CONTINUITY_V1",
            "recording":object["recording"] as? String ?? "UNKNOWN",
            "total_frames":count,"input_numeric_snapshots":rows.count,
            "adjacent_balanced_pairs":verifiedPairCount,
            "observations":observations,"withheld":withheld,
            "authoritative_actions_created":0,"network_calls":0,
            "authority":"EVIDENCE_ONLY_NOT_ACTION_HISTORY"]
}
func fingerprint(_ c:Character) -> String {"sha256:"+String(repeating:String(c),count:64)}
func row(_ hand:String,_ frame:Int,_ pot:String,_ total:String,
         _ wagers:[(String,String)],_ mark:Character) -> [String:Any] {
    let ws=wagers.map { name,amount -> [String:Any] in
        ["amount_bb":amount,"seat_label":name,"identity_status":"EARLIER_FRAME_VERIFIED","player":name]
    }
    return ["hand":hand,"frame":frame,"source_fingerprint":fingerprint(mark),
            "not_authoritative":true,"status":ws.isEmpty ? "BALANCED_NO_WAGERS":"BALANCED_WAGERS",
            "pot_bb":pot,"total_bb":total,"wagers":ws,"unassigned_numeric_labels":[]]
}
func selfTest() throws {
    let rows:[[String:Any]]=[
        row("A",1,"2","5",[("P","3")],"a"),
        row("A",2,"5","5",[],"b"),
        row("A",3,"5","8",[("Q","3")],"c"),
        row("A",4,"5","9",[("Q","4")],"d"),
        row("B",5,"1","1",[],"e"),
        row("B",7,"1","2",[("Q","1")],"f")]
    let input:[String:Any]=["total_frames":7,"authoritative_actions_created":0,
                            "network_calls":0,"numeric_snapshots":rows]
    let result=try project(input)
    let observations=result["observations"] as! [[String:Any]]
    let withheld=result["withheld"] as! [[String:Any]]
    try required(observations.filter{($0["kind"] as? String)=="POT_AND_OUTSTANDING_CONSERVATION_OBSERVED"}.count==1,"COLLECTION_TEST")
    try required(observations.filter{($0["kind"] as? String)=="VERIFIED_SEAT_WAGER_LABEL_APPEARED"}.count==1,"APPEARANCE_TEST")
    try required(observations.filter{($0["kind"] as? String)=="VERIFIED_SEAT_WAGER_LABEL_CHANGED"}.count==1,"DELTA_TEST")
    try required(withheld.count==1,"GAP_TEST")
    try required(result["authoritative_actions_created"] as? Int == 0,"AUTHORITY_TEST")
    var bad=rows
    bad[1]["source_fingerprint"]=fingerprint("a")
    let affected=try project(input.merging(["numeric_snapshots":bad]){_,new in new})
    try required((affected["withheld"] as! [[String:Any]]).contains{
        ($0["reason"] as? String)=="IDENTICAL_IMAGE_WITH_CONFLICTING_NUMERIC_EVIDENCE"},"FORGED_IMAGE_TEST")
    print("NUMERIC_CONTINUITY_SELF_TEST_PASS collection=1 appearance=1 changed=1 gap_withheld=1 forged_image_rejected=YES actions=0")
}
@main struct NumericContinuity {
    static func main() throws {
        let args=CommandLine.arguments
        if args.count==2 && args[1]=="--self-test" {try selfTest();return}
        guard args.count==4 && args[1]=="--project" else {throw ContinuityError("Usage: --self-test | --project <numeric_scan.json> <evidence_only_output.json>")}
        let input=URL(fileURLWithPath:args[2]),output=URL(fileURLWithPath:args[3])
        try required(input.standardizedFileURL.path != output.standardizedFileURL.path,"NO_INPUT_OVERWRITE")
        let raw=try Data(contentsOf:input)
        guard let object=try JSONSerialization.jsonObject(with:raw) as? [String:Any] else {throw ContinuityError("INVALID_INPUT")}
        let result=try project(object)
        let data=try JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys])
        try (data+Data([10])).write(to:output,options:.atomic)
        print("NUMERIC_CONTINUITY_PASS pairs=\(result["adjacent_balanced_pairs"]!) observations=\((result["observations"] as! [Any]).count) withheld=\((result["withheld"] as! [Any]).count) actions=0")
    }
}
