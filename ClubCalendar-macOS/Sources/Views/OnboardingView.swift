import SwiftUI
import ClubCalendarCore

struct OnboardingView: View {
    @Environment(AppState.self) private var appState

    @State private var currentStep = 0
    @State private var clientId = ""
    @State private var clientSecret = ""

    private let totalSteps = 4

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header
                .padding(.top, 30)
                .padding(.bottom, 20)

            // Step content
            stepContent
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding(.horizontal, 40)

            // Navigation
            navigationButtons
                .padding(30)
        }
        .frame(width: 500, height: 450)
        .background(.background)
    }

    // MARK: - Header

    private var header: some View {
        VStack(spacing: 12) {
            Image(systemName: "calendar.badge.clock")
                .font(.system(size: 50))
                .foregroundStyle(.tint)

            Text("Welcome to Club Calendar")
                .font(.title)
                .fontWeight(.semibold)

            // Step indicator
            HStack(spacing: 8) {
                ForEach(0..<totalSteps, id: \.self) { step in
                    Circle()
                        .fill(step <= currentStep ? Color.accentColor : Color.secondary.opacity(0.3))
                        .frame(width: 8, height: 8)
                }
            }
        }
    }

    // MARK: - Step Content

    @ViewBuilder
    private var stepContent: some View {
        switch currentStep {
        case 0:
            credentialsStep
        case 1:
            connectStep
        case 2:
            clubsStep
        case 3:
            calendarStep
        default:
            EmptyView()
        }
    }

    // MARK: - Step 1: Credentials

    private var credentialsStep: some View {
        VStack(spacing: 20) {
            Text("Step 1: Enter Strava API Credentials")
                .font(.headline)

            Text("Create an API application at [strava.com/settings/api](https://www.strava.com/settings/api) to get your Client ID and Secret. Set its Authorization Callback Domain to **callback**.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            VStack(alignment: .leading, spacing: 12) {
                TextField("Client ID", text: $clientId)
                    .textFieldStyle(.roundedBorder)

                SecureField("Client Secret", text: $clientSecret)
                    .textFieldStyle(.roundedBorder)
            }
            .frame(maxWidth: 300)
        }
    }

    // MARK: - Step 2: Connect

    private var connectStep: some View {
        VStack(spacing: 20) {
            Text("Step 2: Connect to Strava")
                .font(.headline)

            Text("Sign in to Strava and authorize Club Calendar to access your clubs and events.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            if appState.isAuthenticated {
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(.green)

                    if let name = appState.athleteName {
                        Text("Connected as \(name)")
                            .font(.callout)
                    } else {
                        Text("Connected to Strava")
                            .font(.callout)
                    }
                }
            } else {
                Button {
                    Task {
                        await appState.authenticate()
                    }
                } label: {
                    HStack {
                        Image(systemName: "link")
                        Text("Connect to Strava")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(appState.isLoading)

                if appState.isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }

            if let error = appState.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
    }

    // MARK: - Step 3: Clubs

    private var clubsStep: some View {
        VStack(spacing: 20) {
            Text("Step 3: Select Clubs to Sync")
                .font(.headline)

            Text("Choose which clubs' events you want to sync to your calendar.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            if appState.settings.syncableClubs.isEmpty {
                VStack(spacing: 12) {
                    if appState.isLoading {
                        ProgressView()
                        Text("Loading clubs...")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("No clubs found")
                            .foregroundStyle(.secondary)

                        Button("Refresh Clubs") {
                            Task {
                                await appState.refreshClubs()
                            }
                        }
                    }
                }
            } else {
                List {
                    ForEach(appState.settings.syncableClubs) { syncable in
                        ClubRow(syncableClub: syncable) { enabled in
                            appState.settings.setClubEnabled(syncable.id, enabled: enabled)
                        }
                    }
                }
                .listStyle(.bordered(alternatesRowBackgrounds: true))
                .frame(height: 150)
            }
        }
        .task {
            if appState.settings.syncableClubs.isEmpty {
                await appState.refreshClubs()
            }
        }
    }

    // MARK: - Step 4: Calendar

    private var calendarStep: some View {
        VStack(spacing: 20) {
            Text("Step 4: Grant Calendar Access")
                .font(.headline)

            Text("Club Calendar needs access to create and update events in your calendar.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            if appState.calendarAccessStatus == .authorized {
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(.green)

                    Text("Calendar access granted")
                        .font(.callout)
                }
            } else {
                Button {
                    Task {
                        await appState.requestCalendarAccess()
                    }
                } label: {
                    HStack {
                        Image(systemName: "calendar")
                        Text("Grant Calendar Access")
                    }
                }
                .buttonStyle(.borderedProminent)
            }

            if appState.calendarAccessStatus == .denied {
                Text("Please enable calendar access in System Settings > Privacy & Security > Calendars")
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
            }
        }
    }

    // MARK: - Navigation

    private var navigationButtons: some View {
        HStack {
            if currentStep > 0 {
                Button("Back") {
                    withAnimation {
                        currentStep -= 1
                    }
                }
                .buttonStyle(.bordered)
            }

            Spacer()

            if currentStep < totalSteps - 1 {
                Button("Continue") {
                    handleContinue()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canContinue)
            } else {
                Button("Get Started") {
                    finishOnboarding()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canFinish)
            }
        }
    }

    // MARK: - Navigation Logic

    private var canContinue: Bool {
        switch currentStep {
        case 0:
            return !clientId.isEmpty && !clientSecret.isEmpty
        case 1:
            return appState.isAuthenticated
        case 2:
            return !appState.settings.enabledClubIds.isEmpty
        default:
            return true
        }
    }

    private var canFinish: Bool {
        appState.calendarAccessStatus == .authorized
    }

    private func handleContinue() {
        switch currentStep {
        case 0:
            // Save credentials before moving to next step
            Task {
                await appState.saveCredentials(clientId: clientId, clientSecret: clientSecret)
                withAnimation {
                    currentStep += 1
                }
            }
        default:
            withAnimation {
                currentStep += 1
            }
        }
    }

    private func finishOnboarding() {
        appState.completeOnboarding()
    }
}

// MARK: - Club Row

struct ClubRow: View {
    let syncableClub: SyncableClub
    let onToggle: (Bool) -> Void

    var body: some View {
        Toggle(isOn: Binding(
            get: { syncableClub.isEnabled },
            set: { onToggle($0) }
        )) {
            VStack(alignment: .leading, spacing: 2) {
                Text(syncableClub.club.name)
                    .font(.body)

                HStack(spacing: 8) {
                    if let city = syncableClub.club.city {
                        Text(city)
                    }
                    Text("\(syncableClub.club.memberCount) members")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
        }
        .toggleStyle(.checkbox)
    }
}
