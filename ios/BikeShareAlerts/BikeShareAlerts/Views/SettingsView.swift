import SwiftUI

struct SettingsView: View {
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Notifications")) {
                    Toggle("Enable Notifications", isOn: .constant(true))
                    Toggle("Smart Alerts", isOn: .constant(true))
                }
                
                Section(header: Text("Account")) {
                    Text("User ID: 1234-5678")
                }
            }
            .navigationTitle("Settings")
        }
    }
}
