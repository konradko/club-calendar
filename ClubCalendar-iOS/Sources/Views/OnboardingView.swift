import SwiftUI
import ClubCalendarCore

struct OnboardingView: View {
    @Environment(AppState.self) private var appState
    @State private var step: Step
    @State private var clientId: String = ""
    @State private var clientSecret: String = ""

    /// Production callers pass nothing — wizard starts at credentials.
    /// Tests pass an explicit step to exercise the deeper branches.
    init(initialStep: Step = .credentials) {
        self._step = State(initialValue: initialStep)
    }

    enum Step: Int, CaseIterable {
        case credentials, connect, clubs, calendar

        var title: String {
            switch self {
            case .credentials: return "API credentials"
            case .connect: return "Connect to Strava"
            case .clubs: return "Pick your clubs"
            case .calendar: return "Calendar access"
            }
        }
    }

    var body: some View {
        NavigationStack {
            VStack {
                progressIndicator
                    .padding(.top, 12)

                Spacer(minLength: 0)

                Group {
                    switch step {
                    case .credentials: credentialsStep
                    case .connect: connectStep
                    case .clubs: clubsStep
                    case .calendar: calendarStep
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()

                Spacer(minLength: 0)

                navigation
                    .padding()
            }
            .navigationTitle(step.title)
            .navigationBarTitleDisplayMode(.inline)
            .task { await appState.refreshState() }
        }
    }

    // MARK: - Steps

    private var credentialsStep: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Create an app at [strava.com/settings/api](https://www.strava.com/settings/api), set its Authorization Callback Domain to **callback**, then paste the Client ID and Client Secret below. They're stored only on this device, in the keychain.")
                .font(.callout)
                .foregroundStyle(.secondary)

            TextField("Client ID", text: $clientId)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)

            SecureField("Client Secret", text: $clientSecret)
                .textFieldStyle(.roundedBorder)

            if let error = appState.errorMessage {
                Text(error).font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private var connectStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "link.circle.fill")
                .font(.system(size: 48))
                .foregroundStyle(.tint)

            Text("Sign in to Strava and authorize Club Calendar to read your clubs and events.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            if appState.isAuthenticated, let name = appState.athleteName {
                Label("Connected as \(name)", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(.green)
            } else {
                Button {
                    Task { await appState.authenticate() }
                } label: {
                    if appState.isLoading {
                        ProgressView()
                    } else {
                        Text("Connect to Strava")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(appState.isLoading)
            }

            if let error = appState.errorMessage {
                Text(error).font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private var clubsStep: some View {
        VStack(spacing: 12) {
            if appState.settings.syncableClubs.isEmpty {
                ContentUnavailableView {
                    Label("Fetch your clubs", systemImage: "person.3")
                } description: {
                    Text("Pull your joined clubs from Strava to pick which ones to sync.")
                } actions: {
                    Button("Fetch clubs") {
                        Task { await appState.refreshClubs() }
                    }
                    .disabled(appState.isLoading)
                }
            } else {
                List {
                    ForEach(appState.settings.syncableClubs) { syncable in
                        Toggle(isOn: Binding(
                            get: { syncable.isEnabled },
                            set: { appState.settings.setClubEnabled(syncable.id, enabled: $0) }
                        )) {
                            Text(syncable.club.name)
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
        }
    }

    private var calendarStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "calendar.circle.fill")
                .font(.system(size: 48))
                .foregroundStyle(.tint)

            Text("Club Calendar writes events into your Apple Calendar. Grant full calendar access so it can dedup and update events.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            switch appState.calendarAccessStatus {
            case .authorized:
                Label("Granted", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(.green)
            case .denied, .restricted:
                Label("Denied — grant access in iOS Settings", systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
            case .notDetermined:
                Button("Grant calendar access") {
                    Task { await appState.requestCalendarAccess() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
    }

    // MARK: - Navigation

    private var progressIndicator: some View {
        HStack(spacing: 8) {
            ForEach(Step.allCases, id: \.rawValue) { s in
                Circle()
                    .fill(s.rawValue <= step.rawValue ? Color.accentColor : Color.secondary.opacity(0.3))
                    .frame(width: 8, height: 8)
            }
        }
    }

    private var navigation: some View {
        HStack {
            if step != .credentials {
                Button("Back") {
                    if let prev = Step(rawValue: step.rawValue - 1) {
                        step = prev
                    }
                }
            }
            Spacer()
            Button(primaryLabel) {
                Task { await advance() }
            }
            .buttonStyle(.borderedProminent)
            .disabled(!canAdvance)
        }
    }

    private var primaryLabel: String {
        step == .calendar ? "Finish" : "Continue"
    }

    private var canAdvance: Bool {
        switch step {
        case .credentials:
            return !clientId.trimmingCharacters(in: .whitespaces).isEmpty
                && !clientSecret.trimmingCharacters(in: .whitespaces).isEmpty
        case .connect:
            return appState.isAuthenticated
        case .clubs:
            return !appState.settings.enabledClubIds.isEmpty
        case .calendar:
            return appState.calendarAccessStatus == .authorized
        }
    }

    private func advance() async {
        switch step {
        case .credentials:
            await appState.saveCredentials(clientId: clientId, clientSecret: clientSecret)
            step = .connect
        case .connect:
            step = .clubs
            if appState.settings.syncableClubs.isEmpty {
                await appState.refreshClubs()
            }
        case .clubs:
            step = .calendar
        case .calendar:
            appState.completeOnboarding()
        }
    }
}
