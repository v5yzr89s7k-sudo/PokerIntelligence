import Foundation
#if canImport(CoreGraphics)
import CoreGraphics
import ImageIO
import CryptoKit
#endif

struct DealerDisc: Codable, Equatable {
    let x: Double
    let yTop: Double
    let width: Double
    let height: Double
    let whiteArea: Int
    let brightRim: Double
    let darkCenter: Double
    let greenSurround: Double
}

struct Raster {
    let w:Int
    let h:Int
    let rgba:[UInt8]
}

func dealerDiscs(_ f:Raster) -> [DealerDisc] {
    let n=f.w*f.h
    guard f.w>=800 && f.h>=400 && f.rgba.count==n*4 else {return []}
    var white=[UInt8](repeating:0,count:n)
    for i in 0..<n {
        let j=i*4
        let r=Int(f.rgba[j]),g=Int(f.rgba[j+1]),b=Int(f.rgba[j+2])
        if r>190 && g>190 && b>190 && abs(r-g)<38 && abs(r-b)<38 {white[i]=1}
    }
    var component=[Int32](repeating:0,count:n)
    var index:Int32=0
    var hits=[DealerDisc]()

    for start in 0..<n where white[start] == 1 && component[start] == 0 {
        index+=1
        var q=[Int]()
        q.reserveCapacity(2048)
        q.append(start)
        component[start]=index
        var head=0, xmin=f.w, xmax=0, ymin=f.h, ymax=0

        while head<q.count {
            let pos=q[head]
            head+=1
            let x=pos%f.w,y=pos/f.w
            xmin=min(xmin,x)
            xmax=max(xmax,x)
            ymin=min(ymin,y)
            ymax=max(ymax,y)

            for dy in -1...1 {
                let yy=y+dy
                if yy<0 || yy>=f.h {continue}
                for dx in -1...1 {
                    if dx == 0 && dy == 0 {continue}
                    let xx=x+dx
                    if xx<0 || xx>=f.w {continue}
                    let next=yy*f.w+xx
                    if white[next] == 1 && component[next] == 0 {
                        component[next]=index
                        q.append(next)
                    }
                }
            }
        }

        let w=xmax-xmin+1,h=ymax-ymin+1,area=q.count
        if !(28...56).contains(w) || !(22...40).contains(h) ||
            !(400...1400).contains(area) {continue}

        let ratio=Double(w)/Double(h)
        let density=Double(area)/Double(w*h)
        if ratio<1.08 || ratio>1.8 || density<0.42 || density>0.75 {continue}

        var rimN=0,rimWhite=0,centerN=0,darkN=0

        for yy in ymin...ymax {
            for xx in xmin...xmax {
                let dx=(Double(xx-xmin)-Double(w-1)/2)/(0.45*Double(w))
                let dy=(Double(yy-ymin)-Double(h-1)/2)/(0.45*Double(h))
                let ell=dx*dx+dy*dy

                if ell>0.45 && ell<0.9 {
                    rimN+=1
                    if component[yy*f.w+xx]==index {rimWhite+=1}
                }

                if ell<0.35 {
                    centerN+=1
                    let pos=(yy*f.w+xx)*4
                    if max(f.rgba[pos],f.rgba[pos+1],f.rgba[pos+2])<115 {
                        darkN+=1
                    }
                }
            }
        }

        guard rimN>0 && centerN>0 else {continue}
        let rim=Double(rimWhite)/Double(rimN)
        let dark=Double(darkN)/Double(centerN)
        if rim<=0.85 || dark<=0.24 || dark>=0.70 {continue}

        let left=max(0,xmin-14),right=min(f.w-1,xmax+14)
        let top=max(0,ymin-14),bottom=min(f.h-1,ymax+14)
        var surroundN=0,greenN=0

        for y in top...bottom {
            for x in left...right {
                if x>=xmin && x<=xmax && y>=ymin && y<=ymax {continue}
                surroundN+=1
                let off=(y*f.w+x)*4
                let r=Double(f.rgba[off])
                let g=Double(f.rgba[off+1])
                let b=Double(f.rgba[off+2])
                if g>45 && g>r*1.25 && g>b*1.10 {greenN+=1}
            }
        }

        guard surroundN>0 else {continue}
        let green=Double(greenN)/Double(surroundN)
        if green<=0.55 {continue}

        hits.append(DealerDisc(
            x:(Double(xmin+xmax)+1)/(2*Double(f.w)),
            yTop:(Double(ymin+ymax)+1)/(2*Double(f.h)),
            width:Double(w)/Double(f.w),
            height:Double(h)/Double(f.h),
            whiteArea:area,
            brightRim:rim,
            darkCenter:dark,
            greenSurround:green
        ))
    }
    return hits.sorted{$0.x<$1.x}
}

#if canImport(CoreGraphics)
func decodeOriginalJPEG(_ url:URL) throws -> Raster {
    guard let source=CGImageSourceCreateWithURL(url as CFURL,nil),
          let original=CGImageSourceCreateImageAtIndex(source,0,nil) else {
        throw NSError(domain:"OriginalJPEG",code:1,userInfo:[
            NSLocalizedDescriptionKey:"Cannot decode original JPEG"
        ])
    }

    let w=1536
    let h=Int(
        (Double(original.height)*Double(w)/Double(original.width)).rounded()
    )
    var rgba=[UInt8](repeating:0,count:w*h*4)

    let ok=rgba.withUnsafeMutableBytes{memory -> Bool in
        guard let context=CGContext(
            data:memory.baseAddress,
            width:w,
            height:h,
            bitsPerComponent:8,
            bytesPerRow:w*4,
            space:CGColorSpaceCreateDeviceRGB(),
            bitmapInfo:CGBitmapInfo.byteOrder32Big.rawValue |
                CGImageAlphaInfo.premultipliedLast.rawValue
        ) else {return false}

        context.interpolationQuality = .high
        context.draw(
            original,
            in:CGRect(x:0,y:0,width:w,height:h)
        )
        return true
    }

    if !ok {throw NSError(domain:"Raster",code:2,userInfo:nil)}
    return Raster(w:w,h:h,rgba:rgba)
}
#endif

#if os(macOS)
struct FrameProof: Codable {
    let hand: String
    let firstFrame: Int
    let confirmedFrame: Int
    let firstFingerprint: String
    let confirmedFingerprint: String
    let dealerPixelX: Double
    let dealerPixelYBottom: Double
    let seatName: String
    let seatDistance: Double
    let rasterOrientation: String
    let authority: String
}

func expect(_ condition:Bool,_ message:String) throws {
    if !condition {
        throw NSError(
            domain:"DEALER_PROOF",
            code:3,
            userInfo:[NSLocalizedDescriptionKey:message]
        )
    }
}

func jsonValue(_ path:URL) throws -> Any {
    try JSONSerialization.jsonObject(with:Data(contentsOf:path))
}

func object(_ value:Any?) throws -> [String:Any] {
    guard let o=value as? [String:Any] else {
        throw NSError(domain:"JSON_OBJECT",code:1,userInfo:nil)
    }
    return o
}

func objects(_ value:Any?) throws -> [[String:Any]] {
    guard let a=value as? [[String:Any]] else {
        throw NSError(domain:"JSON_ARRAY",code:1,userInfo:nil)
    }
    return a
}

func fingerprint(_ bytes:Data) -> String {
    "sha256:"+SHA256.hash(data:bytes).map {
        String(format:"%02x",$0)
    }.joined()
}

func imageAndOCR(
    _ root:URL,
    _ frame:Int,
    _ hand:String,
    _ manifest:[[String:Any]],
    _ board:[[String:Any]]
) throws -> (DealerDisc,[String:(Double,Double)],String) {
    try expect(
        frame>=1 && frame<=manifest.count && frame<=board.count,
        "FRAME_OUT_OF_RANGE"
    )
    let meta=manifest[frame-1]
    let b=board[frame-1]

    try expect(meta["id"] as? Int == frame,"MANIFEST_OWNER")
    let path=meta["file"] as? String ?? ""
    try expect(
        path.hasPrefix("frames/") &&
        !path.contains("..") &&
        !path.hasPrefix("/"),
        "IMAGE_PATH"
    )
    try expect(
        b["hand"] as? String == hand &&
        b["frame"] as? Int == frame &&
        b["visibleBoardCount"] as? Int == 0,
        "PREFLOP_HAND_SCOPE"
    )

    let imageURL=root.appendingPathComponent(path)
    let bytes=try Data(contentsOf:imageURL)
    let sha=fingerprint(bytes)
    let ocr=try object(jsonValue(
        root.appendingPathComponent(
            String(format:"local_ocr/%06d.json",frame)
        )
    ))

    try expect(
        ocr["frame"] as? Int == frame &&
        ocr["sourceFingerprint"] as? String == sha &&
        b["sourceFingerprint"] as? String == sha,
        "ORIGINAL_JPEG_OCR_BOARD_OWNER"
    )

    let capture=try object(ocr["capture"])
    try expect(
        capture["error"] is NSNull || capture["error"] == nil,
        "OCR_ERROR"
    )
    let rows=try objects(capture["lines"])

    let handText=rows.filter { row in
        guard let t=row["text"] as? String else {return false}
        return t.range(
            of:"^Current\\s*:\\s*"+hand+"$",
            options:[.regularExpression,.caseInsensitive]
        ) != nil
    }
    try expect(handText.count==1,"HAND_TEXT_NOT_CONFIRMED")

    let raster=try decodeOriginalJPEG(imageURL)
    let discs=dealerDiscs(raster)
    print(
        "DISC_FRAME",frame,
        "candidates",discs.count,
        "centers",discs.map {
            String(format:"%.5f,%.5f",$0.x,$0.yTop)
        }
    )

    try expect(discs.count==1,"VISUAL_DEALER_DISC_NOT_UNIQUE")

    let names=[
        "Santiago1516jf","GeauxTigaz","luckycryak",
        "urchdog07","Kkos101","poker5068"
    ]
    var seats=[String:(Double,Double)]()

    for name in names {
        let labels=rows.filter {
            $0["text"] as? String == name &&
            ($0["confidence"] as? Double ?? 0)>=0.8
        }

        if labels.count==1,
           let x=labels[0]["x"] as? Double,
           let y=labels[0]["y"] as? Double {
            seats[name]=(x,y)
        }
    }

    try expect(seats.count>=5,"NAMED_SEAT_LABELS_MISSING")
    return (discs[0],seats,sha)
}

func closest(
    _ disc:DealerDisc,
    _ seats:[String:(Double,Double)],
    orientation:String
) -> (String,Double)? {
    let y=orientation == "raster_top"
        ? 1-disc.yTop : disc.yTop

    let distances=seats.map { name,point in
        (name,hypot(disc.x-point.0,y-point.1))
    }.sorted {$0.1<$1.1}

    guard distances.count>=2,
          distances[0].1<0.17,
          distances[1].1-distances[0].1>0.028
    else {return nil}

    return distances[0]
}

func provePair(
    _ root:URL,
    _ hand:String,
    _ first:Int,
    _ second:Int,
    _ expected:String,
    _ manifest:[[String:Any]],
    _ boards:[[String:Any]]
) throws -> [String:FrameProof] {
    try expect(second==first+1,"NONADJACENT_FRAMES")

    let (a,namesA,fpA)=try imageAndOCR(
        root,first,hand,manifest,boards
    )
    let (b,namesB,fpB)=try imageAndOCR(
        root,second,hand,manifest,boards
    )

    try expect(fpA != fpB,"REPEATED_IMAGE")
    try expect(
        abs(a.x-b.x)<0.012 &&
        abs(a.yTop-b.yTop)<0.012,
        "DEALER_ICON_UNSTABLE"
    )

    var outcomes=[String:FrameProof]()

    for orientation in ["raster_top","raster_bottom"] {
        guard let ownerA=closest(
                  a,namesA,orientation:orientation
              ),
              let ownerB=closest(
                  b,namesB,orientation:orientation
              ),
              ownerA.0==ownerB.0 && ownerA.0==expected
        else {continue}

        outcomes[orientation]=FrameProof(
            hand:hand,
            firstFrame:first,
            confirmedFrame:second,
            firstFingerprint:fpA,
            confirmedFingerprint:fpB,
            dealerPixelX:b.x,
            dealerPixelYBottom:orientation == "raster_top"
                ? 1-b.yTop : b.yTop,
            seatName:expected,
            seatDistance:max(ownerA.1,ownerB.1),
            rasterOrientation:orientation,
            authority:
                "TWO_ORIGINAL_FULL_FRAME_DEALER_DISCS; MATCHED_NAMED_BUTTON_SEAT; NO_ACTION_AUTHORITY"
        )
    }

    return outcomes
}

@main struct Main {
    static func main() {
        do {try execute()} catch {
            print("STOP:",error.localizedDescription)
            exit(3)
        }
    }

    static func execute() throws {
        try expect(
            CommandLine.arguments.count==3 ||
            (CommandLine.arguments.count==4 &&
             CommandLine.arguments[3]=="--negatives"),
            "usage: DealerIconNativeProof RECORDING_ROOT OUTPUT_JSON [--negatives]"
        )

        let root=URL(
            fileURLWithPath:CommandLine.arguments[1],
            isDirectory:true
        )
        let out=URL(fileURLWithPath:CommandLine.arguments[2])

        let manifest=try objects(jsonValue(
            root.appendingPathComponent("frames.json")
        ))
        let boards=try objects(jsonValue(
            root.appendingPathComponent("local_board_observations.json")
        ))

        try expect(
            manifest.count==354 && boards.count==354,
            "EXPECTED_354_FRAME_ORIGINAL"
        )

        let first=try provePair(
            root,"2874688303",7,8,"urchdog07",
            manifest,boards
        )
        let second=try provePair(
            root,"2874689539",166,167,"Kkos101",
            manifest,boards
        )

        let intersection=Set(first.keys).intersection(
            Set(second.keys)
        )
        try expect(
            intersection.count==1,
            "DEALER_RASTER_ORIENTATION_NOT_UNIQUE"
        )

        let orientation=intersection.first!
        let rows=[first[orientation]!,second[orientation]!]

        try expect(
            rows.allSatisfy{$0.seatDistance<0.17},
            "BUTTON_NOT_NEAR_OWN_SEAT"
        )

        let encoded=try JSONEncoder().encode(rows)
        let obj=try JSONSerialization.jsonObject(with:encoded)
        let pretty=try JSONSerialization.data(
            withJSONObject:obj,
            options:[.prettyPrinted,.sortedKeys]
        )
        try pretty.write(to:out,options:.atomic)

        if CommandLine.arguments.count==4 {
            let wrongFirst=try provePair(
                root,"2874688303",7,8,"poker5068",
                manifest,boards
            )
            let wrongSecond=try provePair(
                root,"2874689539",166,167,"urchdog07",
                manifest,boards
            )
            try expect(
                wrongFirst.isEmpty && wrongSecond.isEmpty,
                "WRONG_BUTTON_PLAYER_ACCEPTED"
            )

            let empty=Raster(
                w:1536,
                h:992,
                rgba:[UInt8](repeating:0,count:1536*992*4)
            )
            try expect(
                dealerDiscs(empty).isEmpty,
                "BLANK_FRAME_ACCEPTED"
            )
            print(
                "VISUAL_DEALER_NEGATIVES_PASS wrong_hand_button=2 blank=1"
            )
        }

        print(
            "VISUAL_DEALER_ICON_PASS hands=2 original_images=4 hand1=urchdog07 hand2=Kkos101 unknown_bb_preserved=YES actions=0 orientation=",
            orientation
        )
    }
}
#endif
