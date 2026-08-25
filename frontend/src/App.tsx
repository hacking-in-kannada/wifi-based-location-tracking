import { useState } from "react";
import { Radio } from "lucide-react";
import Dashboard from "./pages/Dashboard/Dashboard";
import Training from "./pages/Training/Training";
import Analytics from "./pages/Analytics/Analytics";

function App() {
  const [activeTab, setActiveTab] = useState<"live" | "training" | "analytics">("live");

  return (
    <div className="relative min-h-screen flex flex-col bg-cyber-black text-gray-300">
      {/* Global Glow backgrounds */}
      <div className="grid-backdrop" />
      <div className="orb orb-a" />
      <div className="orb orb-b" />

      {/* Shared Application Top Header */}
      <header className="relative z-10 w-full border-b border-white/5 bg-cyber-gray-dark/85 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-purple-500/10 rounded-lg border border-purple-500/20">
            <Radio className="w-5 h-5 text-neon-purple animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center">
              WiFiSense <span className="ml-2 text-xs font-normal text-gray-500 px-2 py-0.5 bg-white/5 rounded-full">v1.0.0</span>
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              CSI Indoor Motion & Zone Fingerprinting
            </p>
          </div>
        </div>

        {/* Tab Switcher Navigation */}
        <div className="flex space-x-1.5 bg-white/5 p-1 rounded-lg border border-white/5">
          <button
            id="tab-live"
            onClick={() => setActiveTab("live")}
            className={`px-4 py-1.5 rounded-md text-xs font-mono font-bold transition select-none cursor-pointer ${
              activeTab === "live" ? "bg-neon-purple text-cyber-black shadow-md shadow-purple-500/10" : "text-gray-400 hover:text-white"
            }`}
          >
            LIVE MONITOR
          </button>
          <button
            id="tab-training"
            onClick={() => setActiveTab("training")}
            className={`px-4 py-1.5 rounded-md text-xs font-mono font-bold transition select-none cursor-pointer ${
              activeTab === "training" ? "bg-neon-purple text-cyber-black shadow-md shadow-purple-500/10" : "text-gray-400 hover:text-white"
            }`}
          >
            TRAINING STUDIO
          </button>
          <button
            id="tab-analytics"
            onClick={() => setActiveTab("analytics")}
            className={`px-4 py-1.5 rounded-md text-xs font-mono font-bold transition select-none cursor-pointer ${
              activeTab === "analytics" ? "bg-neon-purple text-cyber-black shadow-md shadow-purple-500/10" : "text-gray-400 hover:text-white"
            }`}
          >
            ANALYTICS
          </button>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex flex-col text-right">
            <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Calibration Engine</span>
            <span className="text-xs font-semibold text-white">V1 Calibration Active</span>
          </div>
        </div>
      </header>

      {/* Render active tab page body */}
      <div className="relative z-10 flex-1 flex flex-col">
        {activeTab === "live" ? (
          <Dashboard showHeader={false} />
        ) : activeTab === "training" ? (
          <Training />
        ) : (
          <Analytics />
        )}
      </div>
    </div>
  );
}

export default App;
