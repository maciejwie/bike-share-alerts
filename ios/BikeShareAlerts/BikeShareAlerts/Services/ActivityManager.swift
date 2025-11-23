import CoreMotion
import Combine

class ActivityManager: ObservableObject {
    private let activityManager = CMMotionActivityManager()
    @Published var isCycling: Bool = false
    
    func startTracking() {
        guard CMMotionActivityManager.isActivityAvailable() else { return }
        
        activityManager.startActivityUpdates(to: .main) { [weak self] activity in
            guard let self = self, let activity = activity else { return }
            
            DispatchQueue.main.async {
                self.isCycling = activity.cycling
                if activity.cycling {
                    // Trigger "On the move" mode
                    print("User is cycling!")
                }
            }
        }
    }
    
    func stopTracking() {
        activityManager.stopActivityUpdates()
    }
}
