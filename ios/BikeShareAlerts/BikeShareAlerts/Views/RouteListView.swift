import SwiftUI

struct RouteListView: View {
    // Mock data for now
    @State private var routes = [
        Route(id: UUID(), name: "Home to Work", startStation: "King/Bathurst", endStation: "Bay/Wellington", isActive: true),
        Route(id: UUID(), name: "Work to Gym", startStation: "Bay/Wellington", endStation: "Spadina/College", isActive: false)
    ]
    
    var body: some View {
        NavigationView {
            List {
                ForEach(routes) { route in
                    RouteRow(route: route)
                }
            }
            .navigationTitle("My Routes")
            .toolbar {
                Button(action: {
                    // Add route
                }) {
                    Image(systemName: "plus")
                }
            }
        }
    }
}

struct RouteRow: View {
    let route: Route
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(route.name)
                    .font(.headline)
                Text("\(route.startStation) → \(route.endStation)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if route.isActive {
                Image(systemName: "bell.fill")
                    .foregroundColor(.blue)
            } else {
                Image(systemName: "bell.slash")
                    .foregroundColor(.gray)
            }
        }
        .padding(.vertical, 4)
    }
}
