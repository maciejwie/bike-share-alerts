import CoreLocation
import Combine

class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    @Published var location: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    
    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        manager.allowsBackgroundLocationUpdates = true
        manager.pausesLocationUpdatesAutomatically = false
    }
    
    func requestPermission() {
        manager.requestAlwaysAuthorization()
    }
    
    func startMonitoring() {
        manager.startUpdatingLocation()
        // In a real app, we'd use startMonitoringSignificantLocationChanges() or region monitoring to save battery
    }
    
    func stopMonitoring() {
        manager.stopUpdatingLocation()
    }
    
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        self.location = loc
        // Check proximity to stations here or trigger logic
    }
    
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        self.authorizationStatus = manager.authorizationStatus
    }
}
