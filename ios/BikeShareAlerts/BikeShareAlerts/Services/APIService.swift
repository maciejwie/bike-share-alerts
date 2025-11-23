import Foundation

class APIService: ObservableObject {
    static let shared = APIService()
    private let baseURL = "https://your-vercel-app.vercel.app/api" // Placeholder
    
    @Published var stations: [Station] = []
    
    func fetchStations() async throws -> [Station] {
        guard let url = URL(string: "\(baseURL)/stations") else {
            throw URLError(.badURL)
        }
        
        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(StationResponse.self, from: data)
        return response.stations
    }
    
    func fetchRoutes(userID: String) async throws -> [Route] {
        guard let url = URL(string: "\(baseURL)/routes?user_id=\(userID)") else {
            throw URLError(.badURL)
        }
        
        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(RouteResponse.self, from: data)
        return response.routes
    }
}

struct StationResponse: Codable {
    let stations: [Station]
}

struct RouteResponse: Codable {
    let routes: [Route]
}

struct Station: Identifiable, Codable {
    let id: String
    let bikes: Int
    let ebikes: Int
    let docks: Int
    let lastUpdated: String
    
    enum CodingKeys: String, CodingKey {
        case id, bikes, ebikes, docks
        case lastUpdated = "last_updated"
    }
}
