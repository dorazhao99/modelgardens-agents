// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PrecursorApp",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "PrecursorApp", targets: ["PrecursorApp"])
    ],
    targets: [
        .executableTarget(
            name: "PrecursorApp",
            path: "Sources/PrecursorApp",
            linkerSettings: [
                .linkedLibrary("sqlite3")
            ]
        )
    ]
)


