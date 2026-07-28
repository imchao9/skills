import AppKit
import Foundation
import Vision

guard CommandLine.arguments.count >= 2 else {
    fputs("usage: ocr_scoreboard.swift IMAGE_OR_DIRECTORY [OUTPUT_TSV]\n", stderr)
    exit(2)
}

let inputPath = CommandLine.arguments[1]
let outputPath = CommandLine.arguments.count >= 3 ? CommandLine.arguments[2] : nil
let fileManager = FileManager.default
var isDirectory: ObjCBool = false
guard fileManager.fileExists(atPath: inputPath, isDirectory: &isDirectory) else {
    fputs("input not found: \(inputPath)\n", stderr)
    exit(1)
}

let paths: [String]
if isDirectory.boolValue {
    paths = (try fileManager.contentsOfDirectory(atPath: inputPath))
        .filter { $0.lowercased().hasSuffix(".jpg") || $0.lowercased().hasSuffix(".png") }
        .sorted()
        .map { URL(fileURLWithPath: inputPath).appendingPathComponent($0).path }
} else {
    paths = [inputPath]
}

func recognize(_ path: String) -> String {
    guard
        let image = NSImage(contentsOfFile: path),
        let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil)
    else {
        return ""
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .fast
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    let handler = VNImageRequestHandler(cgImage: cgImage)
    do {
        try handler.perform([request])
    } catch {
        return ""
    }
    let observations = (request.results ?? []).sorted {
        if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.03 {
            return $0.boundingBox.midY > $1.boundingBox.midY
        }
        return $0.boundingBox.minX < $1.boundingBox.minX
    }
    return observations.compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: " ")
        .replacingOccurrences(of: "\t", with: " ")
}

var lines: [String] = []
lines.reserveCapacity(paths.count)
for path in paths {
    autoreleasepool {
        lines.append("\(URL(fileURLWithPath: path).lastPathComponent)\t\(recognize(path))")
    }
}
let payload = lines.joined(separator: "\n") + "\n"
if let outputPath {
    let outputURL = URL(fileURLWithPath: outputPath)
    try fileManager.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try payload.write(toFile: outputPath, atomically: true, encoding: .utf8)
} else {
    print(payload, terminator: "")
}
