
import Foundation
import CoreGraphics
import ImageIO

struct Box {
    var x: Int
    var y: Int
    var w: Int
    var h: Int
    var pixels: Int
}

struct DSU {
    var parents: [Int32] = [0]

    mutating func add() -> Int32 {
        let id = Int32(parents.count)
        parents.append(id)
        return id
    }

    mutating func find(_ id: Int32) -> Int32 {
        var k = Int(id)
        while parents[k] != Int32(k) {
            k = Int(parents[k])
        }
        let root = Int32(k)
        var n = Int(id)
        while parents[n] != root {
            let next = Int(parents[n])
            parents[n] = root
            n = next
        }
        return root
    }

    mutating func merge(_ a: Int32, _ b: Int32) {
        let x = find(a)
        let y = find(b)
        if x != y {
            parents[Int(max(x,y))] = min(x,y)
        }
    }
}

func whiteCardComponents(
    mask: [UInt8], width w: Int, height h: Int
) -> [Box] {
    guard w > 0, h > 0, mask.count == w*h else {
        return []
    }

    var labels = [Int32](repeating:0,count:w*h)
    var dsu = DSU()

    for y in 0..<h {
        for x in 0..<w {
            let i = y*w+x
            if mask[i] == 0 { continue }

            let left: Int32 = x > 0 ? labels[i-1] : 0
            let up: Int32 = y > 0 ? labels[i-w] : 0

            if left == 0 && up == 0 {
                labels[i] = dsu.add()
            } else if left == 0 {
                labels[i] = up
            } else if up == 0 {
                labels[i] = left
            } else {
                labels[i] = left
                if left != up {
                    dsu.merge(left,up)
                }
            }
        }
    }

    let length = dsu.parents.count
    var xmin = [Int](repeating:w,count:length)
    var ymin = [Int](repeating:h,count:length)
    var xmax = [Int](repeating:0,count:length)
    var ymax = [Int](repeating:0,count:length)
    var total = [Int](repeating:0,count:length)

    for y in 0..<h {
        for x in 0..<w {
            let i = y*w+x
            let label = labels[i]
            if label == 0 { continue }

            let root = Int(dsu.find(label))
            total[root] += 1

            xmin[root] = min(xmin[root],x)
            xmax[root] = max(xmax[root],x)
            ymin[root] = min(ymin[root],y)
            ymax[root] = max(ymax[root],y)
        }
    }

    var result = [Box]()

    for i in 1..<length where total[i] > 0 {
        let ww = xmax[i]-xmin[i]+1
        let hh = ymax[i]-ymin[i]+1
        let aspect = Double(hh)/Double(ww)
        let fill = Double(total[i])/Double(ww*hh)

        if Double(ww) >= 0.04*Double(w) &&
           Double(ww) <= 0.14*Double(w) &&
           Double(hh) >= 0.045*Double(h) &&
           Double(hh) <= 0.30*Double(h) &&
           aspect >= 1.04 &&
           aspect <= 1.75 &&
           fill >= 0.57 {
            result.append(Box(
                x:xmin[i],y:ymin[i],
                w:ww,h:hh,pixels:total[i]
            ))
        }
    }

    return result
}

func alignedCardRun(
    _ boxes: [Box], width w: Int, height h: Int
) -> [Box] {
    var best = [Box]()

    for seed in boxes {
        let candidates = boxes.filter { b in
            abs(b.y-seed.y) <= Int(0.03*Double(h)) &&
            abs(b.w-seed.w) <= Int(0.24*Double(seed.w)) &&
            abs(b.h-seed.h) <= Int(0.35*Double(seed.h))
        }.sorted { $0.x < $1.x }

        for start in candidates.indices {
            var run = [candidates[start]]

            if start+1 >= candidates.count {
                continue
            }

            for j in (start+1)..<candidates.count {
                let b = candidates[j]
                let p = run.last!
                let spacing = Double(b.x-p.x)/Double(p.w)

                if spacing >= 0.95 && spacing <= 1.35 {
                    run.append(b)
                } else if spacing > 1.35 {
                    break
                }
            }

            if (3...5).contains(run.count) &&
               run.count > best.count {
                best = run
            }
        }
    }

    return best
}

func visualBoard(_ jpeg: URL) throws -> [Box] {
    guard let src = CGImageSourceCreateWithURL(
        jpeg as CFURL,nil
    ), let image = CGImageSourceCreateImageAtIndex(
        src,0,nil
    ) else {
        throw NSError(
            domain:"PIBoard",code:1,
            userInfo:[
                NSLocalizedDescriptionKey:
                    "Cannot decode JPEG: \(jpeg.path)"
            ]
        )
    }

    let w = min(image.width,1152)
    let h = max(
        1,
        Int(
            (Double(image.height) * Double(w) / Double(image.width)).rounded()
        )
    )

    var rgba = [UInt8](repeating:0,count:w*h*4)

    let drawn: Bool = rgba.withUnsafeMutableBytes { buffer in
        guard let context = CGContext(
            data:buffer.baseAddress,
            width:w,height:h,
            bitsPerComponent:8,
            bytesPerRow:w*4,
            space:CGColorSpaceCreateDeviceRGB(),
            bitmapInfo:
                CGBitmapInfo.byteOrder32Big.rawValue |
                CGImageAlphaInfo.premultipliedLast.rawValue
        ) else {
            return false
        }

        context.interpolationQuality = .high
        context.draw(
            image,
            in:CGRect(
                x:0,y:0,
                width:CGFloat(w),
                height:CGFloat(h)
            )
        )
        return true
    }

    guard drawn else {
        throw NSError(
            domain:"PIBoard",code:2,
            userInfo:[
                NSLocalizedDescriptionKey:
                    "RGBA conversion failed"
            ]
        )
    }

    var mask = [UInt8](repeating:0,count:w*h)

    for i in 0..<(w*h) {
        let r = Int(rgba[i*4])
        let g = Int(rgba[i*4+1])
        let b = Int(rgba[i*4+2])

        let high = max(r,max(g,b))
        let low = min(r,min(g,b))

        if high >= 175 &&
           (high-low)*255 <= high*80 {
            mask[i] = 1
        }
    }

    return alignedCardRun(
        whiteCardComponents(
            mask:mask,width:w,height:h
        ),
        width:w,height:h
    )
}

@main struct Runner {
    static func main() throws {
        let args = CommandLine.arguments

        guard args.count == 3,
              args[1] == "--manifest" else {
            fatalError(
                "Usage: BoardPresence --manifest manifest.tsv"
            )
        }

        let text = try String(
            contentsOf:URL(fileURLWithPath:args[2]),
            encoding:.utf8
        )

        for line in text.split(separator:"\n") {
            let cols = line.split(
                separator:"\t",maxSplits:2
            )

            guard cols.count == 3,
                  let frame = Int(cols[0]) else {
                continue
            }

            let boxes = try visualBoard(
                URL(fileURLWithPath:String(cols[2]))
            )

            let payload: [String:Any] = [
                "frame":frame,
                "hand":String(cols[1]),
                "visible_board_card_count":boxes.count,
                "boxes":boxes.map {
                    [
                        "x":$0.x,"y":$0.y,
                        "width":$0.w,"height":$0.h
                    ]
                }
            ]

            let data = try JSONSerialization.data(
                withJSONObject:payload,
                options:[.sortedKeys]
            )

            print(
                String(decoding:data,as:UTF8.self)
            )
        }
    }
}
