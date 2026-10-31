// Reproducible Perch vector monogram: a single trunk gathering branches.
// The canvas outside the tile stays transparent.
import AppKit
import Foundation

let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let variants: [(String, Int)] = [
    ("icon_16x16", 16), ("icon_16x16@2x", 32),
    ("icon_32x32", 32), ("icon_32x32@2x", 64),
    ("icon_128x128", 128), ("icon_128x128@2x", 256),
    ("icon_256x256", 256), ("icon_256x256@2x", 512),
    ("icon_512x512", 512), ("icon_512x512@2x", 1024)
]

func drawBranch(from: CGPoint, to: CGPoint, width: CGFloat) {
    let path = NSBezierPath()
    path.lineCapStyle = .round
    path.lineWidth = width
    path.move(to: from)
    path.line(to: to)
    path.stroke()
}

func drawNode(center: CGPoint, radius: CGFloat) {
    let node = NSBezierPath(ovalIn: NSRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2))
    node.fill()
}

for (name, size) in variants {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size,
        pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
        isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    let context = NSGraphicsContext(bitmapImageRep: bitmap)!
    NSGraphicsContext.current = context
    context.cgContext.clear(CGRect(x: 0, y: 0, width: size, height: size))
    let scale = CGFloat(size) / 1024
    context.cgContext.scaleBy(x: scale, y: scale)

    // Dark rounded tile: matches the Perch dark interface.
    let bg = NSColor(calibratedRed: 0.06, green: 0.06, blue: 0.06, alpha: 1)
    bg.setFill()
    NSBezierPath(roundedRect: NSRect(x: 64, y: 64, width: 896, height: 896),
                 xRadius: 198, yRadius: 198).fill()

    // Branch color: soft off-white.
    let branchColor = NSColor(calibratedWhite: 0.91, alpha: 1)
    branchColor.setStroke()
    branchColor.setFill()

    // The monogram is built around a single trunk rising from the bottom.
    // Lateral branches angle upward and inward, converging at the crown --
    // many paths (harnesses) feeding one trunk.
    let root = CGPoint(x: 512, y: 210)
    let lowerTrunk = CGPoint(x: 512, y: 420)
    let midTrunk = CGPoint(x: 512, y: 580)
    let upperTrunk = CGPoint(x: 512, y: 720)
    let crown = CGPoint(x: 512, y: 830)

    // Main trunk: thick at the root, tapering toward the crown.
    drawBranch(from: root, to: lowerTrunk, width: 44)
    drawBranch(from: lowerTrunk, to: midTrunk, width: 30)
    drawBranch(from: midTrunk, to: upperTrunk, width: 20)
    drawBranch(from: upperTrunk, to: crown, width: 12)

    // Lower branches: widest reach, converging into the lower trunk.
    drawBranch(from: CGPoint(x: 210, y: 330), to: CGPoint(x: 410, y: 420), width: 18)
    drawBranch(from: CGPoint(x: 814, y: 330), to: CGPoint(x: 614, y: 420), width: 18)

    // Mid branches: medium reach, steeper angle.
    drawBranch(from: CGPoint(x: 250, y: 520), to: CGPoint(x: 430, y: 560), width: 14)
    drawBranch(from: CGPoint(x: 774, y: 520), to: CGPoint(x: 594, y: 560), width: 14)

    // Upper branches: short, almost vertical, merging into the crown area.
    drawBranch(from: CGPoint(x: 360, y: 660), to: CGPoint(x: 470, y: 700), width: 10)
    drawBranch(from: CGPoint(x: 664, y: 660), to: CGPoint(x: 554, y: 700), width: 10)

    // Outer twigs: delicate extensions suggesting a living canopy.
    drawBranch(from: CGPoint(x: 150, y: 460), to: CGPoint(x: 300, y: 490), width: 7)
    drawBranch(from: CGPoint(x: 874, y: 460), to: CGPoint(x: 724, y: 490), width: 7)
    drawBranch(from: CGPoint(x: 300, y: 740), to: CGPoint(x: 440, y: 760), width: 6)
    drawBranch(from: CGPoint(x: 724, y: 740), to: CGPoint(x: 584, y: 760), width: 6)

    // Nodes mark junctions and tips, scaled to stay legible at small sizes.
    let bigNode: CGFloat = 13
    let node: CGFloat = 8
    let tip: CGFloat = 6
    drawNode(center: crown, radius: bigNode)
    drawNode(center: upperTrunk, radius: node)
    drawNode(center: midTrunk, radius: node)
    drawNode(center: lowerTrunk, radius: node)
    drawNode(center: CGPoint(x: 210, y: 330), radius: tip)
    drawNode(center: CGPoint(x: 814, y: 330), radius: tip)
    drawNode(center: CGPoint(x: 150, y: 460), radius: tip)
    drawNode(center: CGPoint(x: 874, y: 460), radius: tip)
    drawNode(center: CGPoint(x: 300, y: 740), radius: tip)
    drawNode(center: CGPoint(x: 724, y: 740), radius: tip)

    NSGraphicsContext.restoreGraphicsState()
    let png = bitmap.representation(using: .png, properties: [:])!
    try png.write(to: output.appendingPathComponent(name + ".png"))
}
