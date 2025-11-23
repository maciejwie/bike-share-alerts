import Foundation

struct Route: Identifiable, Codable {
    let id: UUID
    var name: String
    var startStation: String
    var endStation: String
    var isActive: Bool
}
