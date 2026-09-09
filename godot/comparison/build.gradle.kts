plugins {
    alias(libs.plugins.kotlin.jvm)
    application
}

kotlin { jvmToolchain(21) }

application {
    mainClass.set("dev.partydeck.godot.comparison.ComparisonMainKt")
    applicationName = "partydeck-godot-compare"
}

dependencies {
    implementation(project(":bridge"))
    implementation(libs.serialization.json)
    testImplementation(libs.kotlin.test.junit)
}
