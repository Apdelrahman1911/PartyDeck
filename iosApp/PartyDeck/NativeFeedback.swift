import AVFAudio
import OSLog
import PartyDeckKit
import UIKit

/// Main-thread haptics and a serial audio worker keep cue playback away from the UI hot path.
final class NativeFeedback: NSObject, IosNativeFeedback, AVAudioPlayerDelegate {
    private let logger = Logger(subsystem: "dev.partydeck.app", category: "Feedback")
    private let audioQueue = DispatchQueue(label: "dev.partydeck.feedback.audio", qos: .userInitiated)
    private let selection = UISelectionFeedbackGenerator()
    private let impact = UIImpactFeedbackGenerator(style: .light)
    private let notification = UINotificationFeedbackGenerator()
    private var observers: [NSObjectProtocol] = []
    private var foreground = false
    private var closed = false

    // Accessed only on audioQueue.
    private var players: [String: AVAudioPlayer] = [:]
    private var audioForeground = false
    private var audioClosed = false
    private var audioInterrupted = false
    private var audioActive = false
    private var categoryConfigured = false

    override init() {
        super.init()
        observers.append(NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: AVAudioSession.sharedInstance(),
            queue: .main
        ) { [weak self] notification in
            guard let self,
                  let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
            self.audioQueue.async {
                guard !self.audioClosed else { return }
                self.audioInterrupted = type == .began
                if type == .began { self.stopAudio() }
                // A finished short cue never resumes after a call or another interruption.
            }
        })
        observers.append(NotificationCenter.default.addObserver(
            forName: AVAudioSession.routeChangeNotification,
            object: AVAudioSession.sharedInstance(),
            queue: .main
        ) { [weak self] notification in
            guard let self,
                  let raw = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
                  AVAudioSession.RouteChangeReason(rawValue: raw) == .oldDeviceUnavailable else { return }
            self.audioQueue.async { self.stopAudio() }
        })
    }

    func prepare(key: String, resourceUri: String) {
        guard !closed, let url = URL(string: resourceUri), url.isFileURL else { return }
        audioQueue.async {
            guard !self.audioClosed else { return }
            do {
                let player = try AVAudioPlayer(contentsOf: url)
                player.delegate = self
                player.numberOfLoops = 0
                self.players[key] = player
            } catch {
                self.logger.error("An optional sound cue could not be loaded.")
            }
        }
    }

    func play(key: String, soundEnabled: Bool, hapticsEnabled: Bool) {
        guard !closed, foreground else { return }
        if hapticsEnabled {
            switch key {
            case "ui_tap":
                selection.selectionChanged()
            case "card_place":
                impact.impactOccurred()
            case "challenge":
                notification.notificationOccurred(.warning)
            case "light_out":
                notification.notificationOccurred(.error)
            case "safe", "victory":
                notification.notificationOccurred(.success)
            default:
                break
            }
        }
        audioQueue.async {
            guard !self.audioClosed, self.audioForeground else { return }
            guard soundEnabled else {
                self.stopAudio()
                return
            }
            guard !self.audioInterrupted, let player = self.players[key] else { return }
            do {
                let session = AVAudioSession.sharedInstance()
                if !self.categoryConfigured {
                    try session.setCategory(.ambient, mode: .default, options: [])
                    self.categoryConfigured = true
                }
                if !self.audioActive {
                    try session.setActive(true)
                    self.audioActive = true
                }
                // One audible cue at a time keeps feedback bounded and avoids stacked peaks.
                self.players.values.forEach { $0.stop() }
                player.currentTime = 0
                if !player.play() {
                    self.logger.error("An optional sound cue could not start.")
                    self.stopAudio()
                }
            } catch {
                self.logger.error("Optional game audio is currently unavailable.")
                self.stopAudio()
            }
        }
    }

    func setForeground(value: Bool) {
        guard !closed else { return }
        foreground = value
        audioQueue.async {
            self.audioForeground = value
            if !value { self.stopAudio() }
        }
    }

    func close() {
        guard !closed else { return }
        closed = true
        foreground = false
        observers.forEach { NotificationCenter.default.removeObserver($0) }
        observers.removeAll()
        audioQueue.async {
            self.audioClosed = true
            self.audioForeground = false
            self.stopAudio()
            self.players.removeAll()
        }
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        if !flag { logger.error("An optional sound cue ended unexpectedly.") }
        audioQueue.async {
            if self.players.values.allSatisfy({ !$0.isPlaying }) { self.deactivateAudio() }
        }
    }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        logger.error("An optional sound cue could not be decoded.")
        audioQueue.async { self.stopAudio() }
    }

    private func stopAudio() {
        players.values.forEach {
            $0.stop()
            $0.currentTime = 0
        }
        deactivateAudio()
    }

    private func deactivateAudio() {
        guard audioActive else { return }
        do {
            try AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
            audioActive = false
        } catch {
            logger.error("The audio session could not be released immediately.")
        }
    }

    deinit {
        observers.forEach { NotificationCenter.default.removeObserver($0) }
    }
}
