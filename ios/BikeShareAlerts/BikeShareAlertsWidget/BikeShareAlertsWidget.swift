import WidgetKit
import SwiftUI

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> SimpleEntry {
        SimpleEntry(date: Date(), status: "Loading...")
    }

    func getSnapshot(in context: Context, completion: @escaping (SimpleEntry) -> ()) {
        let entry = SimpleEntry(date: Date(), status: "Good Availability")
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
        let entries = [SimpleEntry(date: Date(), status: "Good Availability")]
        let timeline = Timeline(entries: entries, policy: .atEnd)
        completion(timeline)
    }
}

struct SimpleEntry: TimelineEntry {
    let date: Date
    let status: String
}

struct BikeShareAlertsWidgetEntryView : View {
    var entry: Provider.Entry

    var body: some View {
        VStack {
            Text("Bike Share")
                .font(.caption)
            Text(entry.status)
                .font(.headline)
        }
    }
}

@main
struct BikeShareAlertsWidget: Widget {
    let kind: String = "BikeShareAlertsWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            BikeShareAlertsWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Route Status")
        .description("Shows the status of your active route.")
    }
}
