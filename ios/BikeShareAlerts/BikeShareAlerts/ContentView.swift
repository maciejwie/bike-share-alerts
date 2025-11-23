import SwiftUI

struct ContentView: View {
    @StateObject private var activityManager = ActivityManager()
    
    var body: some View {
        Group {
            if activityManager.isCycling {
                CyclingModeView()
            } else {
                TabView {
                    RouteListView()
                        .tabItem {
                            Label("Routes", systemImage: "map")
                        }
                    
                    SettingsView()
                        .tabItem {
                            Label("Settings", systemImage: "gear")
                        }
                }
            }
        }
        .onAppear {
            activityManager.startTracking()
        }
    }
}

struct CyclingModeView: View {
    var body: some View {
        VStack {
            Image(systemName: "bicycle")
                .font(.system(size: 80))
                .foregroundColor(.green)
            Text("Cycling Mode Active")
                .font(.largeTitle)
                .bold()
            Text("Monitoring destination docks...")
                .foregroundColor(.secondary)
        }
    }
}
