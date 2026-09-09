import AVFoundation
import UIKit

/// AVFoundation only produces QR metadata. Frames are never stored, uploaded, or handed to Kotlin.
final class QRScannerViewController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "dev.partydeck.camera.session", qos: .userInitiated)
    private let metadataQueue = DispatchQueue(label: "dev.partydeck.camera.metadata", qos: .userInitiated)
    private let preview = CameraPreviewView()
    private let instruction = UILabel()
    private let status = UILabel()
    private let settingsButton = UIButton(type: .system)
    private let retryButton = UIButton(type: .system)
    private var completion: ((String?) -> Void)?
    private var observers: [NSObjectProtocol] = []
    private var visible = false
    private var foreground = true
    private var permissionRequestStarted = false
    private var completed = false

    // Accessed only on sessionQueue.
    private var configured = false
    private var captureClosed = false
    private var metadataOutput: AVCaptureMetadataOutput?

    init(completion: @escaping (String?) -> Void) {
        self.completion = completion
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { return nil }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = NSLocalizedString("scan.title", value: "Scan invitation", comment: "QR scanner title")
        view.backgroundColor = UIColor(red: 25 / 255, green: 21 / 255, blue: 38 / 255, alpha: 1)
        navigationItem.leftBarButtonItem = UIBarButtonItem(barButtonSystemItem: .cancel, target: self, action: #selector(cancelTapped))
        navigationItem.leftBarButtonItem?.accessibilityIdentifier = "scan-cancel"
        navigationController?.navigationBar.tintColor = UIColor(red: 214 / 255, green: 239 / 255, blue: 130 / 255, alpha: 1)

        preview.previewLayer.session = session
        preview.previewLayer.videoGravity = .resizeAspectFill
        preview.layer.cornerRadius = 24
        preview.clipsToBounds = true
        preview.backgroundColor = .black
        preview.isAccessibilityElement = false

        instruction.text = NSLocalizedString("scan.instructions", value: "Point your camera at the host’s QR code.\nYou’ll confirm before joining.", comment: "QR scanning instructions")
        instruction.font = .preferredFont(forTextStyle: .body)
        instruction.adjustsFontForContentSizeCategory = true
        instruction.numberOfLines = 0
        instruction.textAlignment = .center

        status.font = .preferredFont(forTextStyle: .subheadline)
        status.adjustsFontForContentSizeCategory = true
        status.numberOfLines = 0
        status.textAlignment = .center
        status.textColor = .secondaryLabel
        status.accessibilityIdentifier = "scan-status"

        settingsButton.setTitle(NSLocalizedString("scan.settings", value: "Open Settings", comment: "Open app settings"), for: .normal)
        settingsButton.titleLabel?.font = .preferredFont(forTextStyle: .headline)
        settingsButton.titleLabel?.adjustsFontForContentSizeCategory = true
        settingsButton.addTarget(self, action: #selector(openSettings), for: .touchUpInside)
        settingsButton.isHidden = true

        retryButton.setTitle(NSLocalizedString("scan.retry", value: "Try camera again", comment: "Retry camera capture"), for: .normal)
        retryButton.titleLabel?.font = .preferredFont(forTextStyle: .headline)
        retryButton.titleLabel?.adjustsFontForContentSizeCategory = true
        retryButton.addTarget(self, action: #selector(retryCapture), for: .touchUpInside)
        retryButton.isHidden = true

        let controls = UIStackView(arrangedSubviews: [instruction, status, settingsButton, retryButton])
        controls.axis = .vertical
        controls.spacing = 12
        let scroll = UIScrollView()
        scroll.alwaysBounceVertical = false
        scroll.translatesAutoresizingMaskIntoConstraints = false
        let content = UIStackView(arrangedSubviews: [preview, controls])
        content.axis = .vertical
        content.spacing = 20
        content.translatesAutoresizingMaskIntoConstraints = false
        controls.translatesAutoresizingMaskIntoConstraints = false
        preview.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(scroll)
        scroll.addSubview(content)
        let guide = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            scroll.topAnchor.constraint(equalTo: guide.topAnchor),
            scroll.bottomAnchor.constraint(equalTo: guide.bottomAnchor),
            scroll.leadingAnchor.constraint(equalTo: guide.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: guide.trailingAnchor),
            content.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor, constant: 16),
            content.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor, constant: -20),
            content.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor, constant: 20),
            content.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor, constant: -20),
            content.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor, constant: -40),
            preview.heightAnchor.constraint(equalTo: guide.heightAnchor, multiplier: 0.55),
            settingsButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 48),
            retryButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 48),
        ])
        observeCapture()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        visible = true
        requestCameraWhenNeeded()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        visible = false
        updateCapture()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        if let connection = preview.previewLayer.connection,
           connection.isVideoOrientationSupported,
           let orientation = view.window?.windowScene?.interfaceOrientation {
            switch orientation {
            case .portrait: connection.videoOrientation = .portrait
            case .portraitUpsideDown: connection.videoOrientation = .portraitUpsideDown
            case .landscapeLeft: connection.videoOrientation = .landscapeLeft
            case .landscapeRight: connection.videoOrientation = .landscapeRight
            default: break
            }
        }
    }

    func setForeground(_ value: Bool) {
        foreground = value
        if isViewLoaded {
            preview.isHidden = !value
            if value, visible { requestCameraWhenNeeded() }
            else { updateCapture() }
        }
    }

    func cancelFromOwner() { finish(nil, animated: false) }

    private func requestCameraWhenNeeded() {
        guard !completed else { return }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            settingsButton.isHidden = true
            status.text = NSLocalizedString("scan.privacy", value: "Camera images stay on this device.", comment: "QR camera privacy note")
            updateCapture()
        case .notDetermined:
            guard !permissionRequestStarted else { return }
            permissionRequestStarted = true
            AVCaptureDevice.requestAccess(for: .video) { [weak self] _ in
                DispatchQueue.main.async { self?.requestCameraWhenNeeded() }
            }
        case .denied:
            preview.isHidden = true
            status.text = NSLocalizedString("scan.denied", value: "Camera access is off. Allow it in Settings, or cancel and paste an invitation.", comment: "Camera access denied")
            settingsButton.isHidden = false
            updateCapture()
        case .restricted:
            preview.isHidden = true
            status.text = NSLocalizedString("scan.restricted", value: "Camera access is unavailable on this device. Cancel to paste an invitation instead.", comment: "Camera access restricted")
            settingsButton.isHidden = true
            updateCapture()
        @unknown default:
            showCameraFailure()
        }
    }

    private func updateCapture() {
        let shouldRun = visible && foreground && !completed && AVCaptureDevice.authorizationStatus(for: .video) == .authorized
        preview.isHidden = !shouldRun
        sessionQueue.async { [weak self] in
            guard let self, !self.captureClosed else { return }
            if shouldRun {
                do {
                    try self.configureIfNeeded()
                    if !self.session.isRunning { self.session.startRunning() }
                } catch {
                    DispatchQueue.main.async { [weak self] in self?.showCameraFailure() }
                }
            } else if self.session.isRunning {
                self.session.stopRunning()
            }
        }
    }

    private func configureIfNeeded() throws {
        guard !configured else { return }
        guard let camera = AVCaptureDevice.default(for: .video) else { throw CameraFailure.unavailable }
        let input = try AVCaptureDeviceInput(device: camera)
        let output = AVCaptureMetadataOutput()
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .high
        guard session.canAddInput(input) else { throw CameraFailure.unavailable }
        session.addInput(input)
        guard session.canAddOutput(output) else {
            session.removeInput(input)
            throw CameraFailure.unavailable
        }
        session.addOutput(output)
        guard output.availableMetadataObjectTypes.contains(.qr) else {
            session.removeOutput(output)
            session.removeInput(input)
            throw CameraFailure.unavailable
        }
        output.setMetadataObjectsDelegate(self, queue: metadataQueue)
        output.metadataObjectTypes = [.qr]
        metadataOutput = output
        configured = true
    }

    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput metadataObjects: [AVMetadataObject], from connection: AVCaptureConnection) {
        guard let value = metadataObjects.compactMap({ $0 as? AVMetadataMachineReadableCodeObject })
            .first(where: { $0.type == .qr })?.stringValue else { return }
        DispatchQueue.main.async { [weak self] in
            guard let self, !self.completed, self.foreground, self.visible else { return }
            // This is a UX filter; the common invitation decoder performs authoritative validation.
            guard value.hasPrefix("partydeck:v1:"), value.utf8.count <= 2_048 else {
                self.status.text = NSLocalizedString("scan.other_code", value: "That code isn’t a PartyDeck invitation. Ask the host to show their table’s QR code.", comment: "Unrelated QR code")
                return
            }
            self.finish(value, animated: !UIAccessibility.isReduceMotionEnabled)
        }
    }

    private func observeCapture() {
        let center = NotificationCenter.default
        observers.append(center.addObserver(forName: AVCaptureSession.runtimeErrorNotification, object: session, queue: .main) { [weak self] _ in
            self?.showCameraFailure()
        })
        observers.append(center.addObserver(forName: AVCaptureSession.wasInterruptedNotification, object: session, queue: .main) { [weak self] _ in
            self?.preview.isHidden = true
            self?.status.text = NSLocalizedString("scan.interrupted", value: "The camera is paused. Keep this screen open to continue scanning.", comment: "Camera temporarily interrupted")
        })
        observers.append(center.addObserver(forName: AVCaptureSession.interruptionEndedNotification, object: session, queue: .main) { [weak self] _ in
            self?.requestCameraWhenNeeded()
        })
    }

    private func showCameraFailure() {
        guard !completed else { return }
        preview.isHidden = true
        status.text = NSLocalizedString("scan.unavailable", value: "The camera couldn’t start. Try again, or cancel and paste an invitation.", comment: "Camera capture failed")
        retryButton.isHidden = false
        sessionQueue.async { [weak self] in
            guard let self, self.session.isRunning else { return }
            self.session.stopRunning()
        }
    }

    private func finish(_ value: String?, animated: Bool) {
        guard !completed else { return }
        completed = true
        preview.isHidden = true
        observers.forEach { NotificationCenter.default.removeObserver($0) }
        observers.removeAll()
        sessionQueue.async {
            self.captureClosed = true
            if self.session.isRunning { self.session.stopRunning() }
            self.metadataOutput?.setMetadataObjectsDelegate(nil, queue: nil)
            self.session.inputs.forEach { self.session.removeInput($0) }
            self.session.outputs.forEach { self.session.removeOutput($0) }
            self.metadataOutput = nil
        }
        let callback = completion
        completion = nil
        let presented = navigationController ?? self
        if presented.presentingViewController != nil {
            presented.dismiss(animated: animated) { callback?(value) }
        } else {
            callback?(value)
        }
    }

    @objc private func cancelTapped() { finish(nil, animated: !UIAccessibility.isReduceMotionEnabled) }

    @objc private func openSettings() {
        guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
        UIApplication.shared.open(url, options: [:])
    }

    @objc private func retryCapture() {
        retryButton.isHidden = true
        requestCameraWhenNeeded()
    }

    deinit {
        observers.forEach { NotificationCenter.default.removeObserver($0) }
    }
}

private final class CameraPreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
}

private enum CameraFailure: Error { case unavailable }
