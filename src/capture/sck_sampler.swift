import Foundation
import ScreenCaptureKit
import CoreMedia
import CoreVideo
import Darwin

final class LatestFrameStreamer: NSObject, SCStreamOutput {
    private let socketPath = "/tmp/poker_intelligence_frame.sock"
    private var serverFD: Int32 = -1
    private var clientFD: Int32 = -1

    private let width = 934
    private let height = 696
    private let bytesPerPixel = 4

    private var lastSent = CFAbsoluteTimeGetCurrent()
    private let minimumSendInterval = 1.0 / 30.0

    override init() {
        super.init()
        setupSocket()
    }

    deinit {
        if clientFD >= 0 {
            close(clientFD)
        }

        if serverFD >= 0 {
            close(serverFD)
        }

        unlink(socketPath)
    }

    private func setupSocket() {
        unlink(socketPath)

        serverFD = socket(AF_UNIX, SOCK_STREAM, 0)

        guard serverFD >= 0 else {
            fatalError("socket() failed")
        }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)

        let pathBytes = socketPath.utf8CString

        let sunPathCapacity = MemoryLayout.size(
            ofValue: addr.sun_path
        )

        withUnsafeMutablePointer(to: &addr.sun_path) {
            $0.withMemoryRebound(
                to: CChar.self,
                capacity: sunPathCapacity
            ) { ptr in
                for i in 0..<min(
                    pathBytes.count,
                    sunPathCapacity
                ) {
                    ptr[i] = pathBytes[i]
                }
            }
        }

        let len = socklen_t(
            MemoryLayout<sockaddr_un>.size
        )

        let bindResult = withUnsafePointer(
            to: &addr
        ) {
            $0.withMemoryRebound(
                to: sockaddr.self,
                capacity: 1
            ) {
                Darwin.bind(serverFD, $0, len)
            }
        }

        guard bindResult == 0 else {
            fatalError("bind() failed")
        }

        guard Darwin.listen(serverFD, 1) == 0 else {
            fatalError("listen() failed")
        }

        print(
            "[SCK] waiting for Python consumer:",
            socketPath
        )

        clientFD = Darwin.accept(
            serverFD,
            nil,
            nil
        )

        guard clientFD >= 0 else {
            fatalError("accept() failed")
        }

        print("[SCK] Python consumer connected")
    }

    private func sendAll(
        _ pointer: UnsafeRawPointer,
        count: Int
    ) -> Bool {
        var sent = 0

        while sent < count {
            let n = Darwin.send(
                clientFD,
                pointer.advanced(by: sent),
                count - sent,
                0
            )

            if n <= 0 {
                return false
            }

            sent += n
        }

        return true
    }

    func stream(
        _ stream: SCStream,
        didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of outputType: SCStreamOutputType
    ) {
        guard outputType == .screen else {
            return
        }

        let now = CFAbsoluteTimeGetCurrent()

        if now - lastSent < minimumSendInterval {
            return
        }

        lastSent = now

        guard let imageBuffer =
            CMSampleBufferGetImageBuffer(
                sampleBuffer
            )
        else {
            return
        }

        CVPixelBufferLockBaseAddress(
            imageBuffer,
            .readOnly
        )

        defer {
            CVPixelBufferUnlockBaseAddress(
                imageBuffer,
                .readOnly
            )
        }

        guard let base =
            CVPixelBufferGetBaseAddress(
                imageBuffer
            )
        else {
            return
        }

        let sourceWidth =
            CVPixelBufferGetWidth(
                imageBuffer
            )

        let sourceHeight =
            CVPixelBufferGetHeight(
                imageBuffer
            )

        let bytesPerRow =
            CVPixelBufferGetBytesPerRow(
                imageBuffer
            )

        guard
            sourceWidth == width,
            sourceHeight == height
        else {
            print(
                "[SCK] unexpected frame size",
                sourceWidth,
                sourceHeight
            )
            return
        }

        let payloadSize =
            width
            * height
            * bytesPerPixel

        var header = UInt32(
            payloadSize
        ).bigEndian

        let headerOK =
            withUnsafePointer(
                to: &header
            ) {
                sendAll(
                    $0,
                    count: 4
                )
            }

        guard headerOK else {
            return
        }

        if bytesPerRow == width * bytesPerPixel {
            _ = sendAll(
                base,
                count: payloadSize
            )
        } else {
            for row in 0..<height {
                let rowPtr =
                    base.advanced(
                        by: row * bytesPerRow
                    )

                let ok = sendAll(
                    rowPtr,
                    count:
                        width * bytesPerPixel
                )

                if !ok {
                    return
                }
            }
        }
    }
}


@main
struct Main {
    static func main() async throws {
        print(
            "POKER INTELLIGENCE — FAST SAMPLER V1"
        )

        let content =
            try await SCShareableContent
                .excludingDesktopWindows(
                    false,
                    onScreenWindowsOnly: true
                )

        let windows = content.windows

        print("[SCK] visible ScreenCaptureKit windows:")

        for window in windows {
            let app = (
                window.owningApplication?
                    .applicationName
                ?? ""
            )

            print(
                "[SCK_WINDOW]",
                "id=\(window.windowID)",
                "app=\(app)",
                "title=\(window.title ?? "")",
                "frame=\(window.frame)"
            )
        }

        let acrWindows = windows.filter { window in
            let app = (
                window.owningApplication?
                    .applicationName
                ?? ""
            )

            return (
                app == "ACRPoker"
                || app == "Electron"
            )
        }

        guard !acrWindows.isEmpty else {
            fatalError(
                "No visible Electron / ACR window found"
            )
        }

        let tableCandidates = acrWindows.filter { window in
            let title = (
                window.title
                ?? ""
            )

            return (
                !title.isEmpty
                && title != "ACR Poker Lobby"
                && title.contains("Hold'em")
                && title.contains("No Limit")
            )
        }

        guard let targetWindow =
            tableCandidates.first
        else {
            print(
                "[SCK] Electron windows found, "
                + "but no poker table window is open."
            )

            for window in acrWindows {
                print(
                    "[SCK_ACR]",
                    "title=\(window.title ?? "")",
                    "frame=\(window.frame)"
                )
            }

            fatalError(
                "Open an ACR poker table and rerun"
            )
        }

        print()
        print(
            "[SCK] TARGET TABLE:",
            targetWindow.title ?? ""
        )

        print(
            "[SCK] TARGET FRAME:",
            targetWindow.frame
        )

        guard let targetDisplay = content.displays.first(
            where: { display in
                let df = display.frame
                let wf = targetWindow.frame

                return (
                    wf.midX >= df.minX
                    && wf.midX <= df.maxX
                    && wf.midY >= df.minY
                    && wf.midY <= df.maxY
                )
            }
        ) else {
            fatalError(
                "Could not resolve display containing ACR table"
            )
        }

        print(
            "[SCK] TARGET DISPLAY:",
            targetDisplay.displayID,
            targetDisplay.frame
        )

        let filter = SCContentFilter(
            display: targetDisplay,
            including: [targetWindow]
        )

        let config =
            SCStreamConfiguration()

        // The filter is display-scoped because direct
        // desktopIndependentWindow capture is unstable in this
        // command-line process. Therefore explicitly crop the
        // display coordinate space to the ACR window rectangle.
        //
        // This is critical: output pixel (0,0) must correspond
        // to poker-table pixel (0,0), otherwise every existing
        // 934x696 geometry ROI is displaced/scaled.
        let displayFrame = targetDisplay.frame
        let windowFrame = targetWindow.frame

        let sourceRect = CGRect(
            x: windowFrame.minX - displayFrame.minX,
            y: windowFrame.minY - displayFrame.minY,
            width: windowFrame.width,
            height: windowFrame.height
        )

        config.sourceRect = sourceRect

        print(
            "[SCK] SOURCE RECT:",
            sourceRect
        )

        // Produce the exact canonical image expected by the
        // existing Poker Intelligence geometry.
        config.width = 934
        config.height = 696

        config.minimumFrameInterval =
            CMTime(
                value: 1,
                timescale: 60
            )

        config.queueDepth = 3

        config.pixelFormat =
            kCVPixelFormatType_32BGRA

        config.showsCursor = false

        let streamer =
            LatestFrameStreamer()

        let stream = SCStream(
            filter: filter,
            configuration: config,
            delegate: nil
        )

        let queue =
            DispatchQueue(
                label:
                    "poker.intelligence.fast.sampler"
            )

        try stream.addStreamOutput(
            streamer,
            type: .screen,
            sampleHandlerQueue: queue
        )

        try await stream.startCapture()

        print("[SCK] capture started")

        while true {
            try await Task.sleep(
                for: .seconds(60)
            )
        }
    }
}
