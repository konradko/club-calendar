import SwiftUI

struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gear")
                }

            ClubsSettingsView()
                .tabItem {
                    Label("Clubs", systemImage: "person.3")
                }

            AccountSettingsView()
                .tabItem {
                    Label("Account", systemImage: "person.circle")
                }
        }
        .frame(width: 450, height: 300)
    }
}
