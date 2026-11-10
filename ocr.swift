import Foundation
import Vision
import AppKit
// 作業AI saboranai／kanpi 用の文字読み（作業者の道具とは別に持つ）
// usage: ocr <image>...  → 1行1画像のJSON {"p":path,"r":[[text,x,y,w,h,conf],...]}（座標は左上原点・0〜1）
for p in CommandLine.arguments.dropFirst() {
    autoreleasepool {
        guard let img = NSImage(contentsOfFile: p), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("{\"p\":\"\(p)\",\"r\":null}"); return }
        let req = VNRecognizeTextRequest()
        req.recognitionLanguages = ["ja-JP", "en-US"]
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = false
        try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
        var rows: [[Any]] = []
        for o in req.results ?? [] {
            guard let c = o.topCandidates(1).first else { continue }
            let b = o.boundingBox
            rows.append([c.string, Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height), Double(c.confidence)])
        }
        let d: [String: Any] = ["p": p, "r": rows]
        if let j = try? JSONSerialization.data(withJSONObject: d), let s = String(data: j, encoding: .utf8) { print(s) }
        fflush(stdout)
    }
}
