import SwiftUI

struct AccountSettingsView: View {
    @Environment(AppState.self) private var appState

    @State private var clientId = ""
    @State private var clientSecret = ""
    @State private var showingCredentialsEditor = false

    var body: some View {
        Form {
            // Connection status
            Section("Strava Connection") {
                if appState.isAuthenticated {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)

                        if let name = appState.athleteName {
                            Text("Connected as \(name)")
                        } else {
                            Text("Connected to Strava")
                        }
                    }

                    Button("Disconnect from Strava", role: .destructive) {
                        Task {
                            await appState.disconnect()
                        }
                    }
                } else {
                    HStack {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.red)
                        Text("Not connected")
                    }

                    if appState.hasAPICredentials {
                        Button("Connect to Strava") {
                            Task {
                                await appState.authenticate()
                            }
                        }
                        .disabled(appState.isLoading)
                    } else {
                        Text("Enter API credentials below to connect")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            // API Credentials
            Section("Strava API") {
                if showingCredentialsEditor {
                    credentialsEditor
                } else {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            if appState.hasAPICredentials {
                                Label("Credentials configured", systemImage: "key.fill")
                                    .foregroundStyle(.secondary)
                            } else {
                                Label("No credentials configured", systemImage: "key")
                                    .foregroundStyle(.orange)
                            }
                        }

                        Spacer()

                        Button(appState.hasAPICredentials ? "Update" : "Add") {
                            showingCredentialsEditor = true
                        }
                    }
                }

                Button("Open Strava API Settings") {
                    if let url = URL(string: "https://www.strava.com/settings/api") {
                        NSWorkspace.shared.open(url)
                    }
                }
                .buttonStyle(.link)
            }

            // Error display
            if let error = appState.errorMessage {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.callout)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    private var credentialsEditor: some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("Client ID", text: $clientId)
                .textFieldStyle(.roundedBorder)

            SecureField("Client Secret", text: $clientSecret)
                .textFieldStyle(.roundedBorder)

            HStack {
                Button("Cancel") {
                    clientId = ""
                    clientSecret = ""
                    showingCredentialsEditor = false
                }
                .buttonStyle(.bordered)

                Button("Save") {
                    Task {
                        await appState.saveCredentials(clientId: clientId, clientSecret: clientSecret)
                        clientId = ""
                        clientSecret = ""
                        showingCredentialsEditor = false
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(clientId.isEmpty || clientSecret.isEmpty)
            }
        }
    }
}
