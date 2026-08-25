import { useEffect, useRef, useState } from "react";
import { 
  Activity, 
  Wifi, 
  Terminal, 
  History, 
  Eye, 
  Zap, 
  Radio
} from "lucide-react";

interface PredictionPayload {
  position_id: number;
  label: string;
  confidence: number;
  x_pct: number;
  y_pct: number;
  image_path?: string;
  timestamp: string;
}

interface MotionPayload {
  state: string;
  variance: number;
  direction: string;
  speed: string;
  timestamp: string;
}

interface HealthPayload {
  rssi: number;
  packet_rate: number;
  device_connected: boolean;
  latency_ms: number;
  timestamp: string;
}

interface LogPayload {
  message: string;
  timestamp: string;
}

interface TrailItem {
  x_pct: number;
  y_pct: number;
  timestamp: Date;
}

export default function Dashboard({ showHeader = true }: { showHeader?: boolean }) {
  const [socketConnected, setSocketConnected] = useState<boolean>(false);
  const [activeRoom, setActiveRoom] = useState<{ id: number; name: string } | null>(null);
  const [blueprintImg, setBlueprintImg] = useState<HTMLImageElement | null>(null);
  const [roomPositions, setRoomPositions] = useState<Array<{ id: number; label: string; x_pct: number; y_pct: number }>>([]);
  
  // Real-time telemetry
  const [prediction, setPrediction] = useState<PredictionPayload | null>(null);
  const [motion, setMotion] = useState<MotionPayload | null>({
    state: "NO_MOTION",
    variance: 0.04,
    direction: "stationary",
    speed: "none",
    timestamp: new Date().toISOString()
  });
  const [health, setHealth] = useState<HealthPayload>({
    rssi: -60,
    packet_rate: 0.0,
    device_connected: false,
    latency_ms: 0.0,
    timestamp: new Date().toISOString()
  });

  // History logs lists
  const [predictionHistory, setPredictionHistory] = useState<PredictionPayload[]>([]);
  const [motionEvents, setMotionEvents] = useState<MotionPayload[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  
  // Toggles
  const [showHeatmap, setShowHeatmap] = useState<boolean>(false);
  const [showTrail, setShowTrail] = useState<boolean>(false);
  const [trail, setTrail] = useState<TrailItem[]>([]);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const logTerminalRef = useRef<HTMLDivElement | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  // Load active room, blueprint image, and configured room positions on mount
  useEffect(() => {
    const loadActiveRoom = async () => {
      try {
        const res = await fetch(`http://${window.location.hostname}:8000/api/v1/rooms`);
        if (!res.ok) return;
        const rooms = await res.json();
        if (rooms && rooms.length > 0) {
          const r = rooms[0];
          setActiveRoom({ id: r.id, name: r.name });
          
          if (r.blueprint && r.blueprint.file_path) {
            const img = new Image();
            img.crossOrigin = "anonymous";
            img.src = `http://${window.location.hostname}:8000/${r.blueprint.file_path}`;
            img.onload = () => setBlueprintImg(img);
          }

          if (r.positions && r.blueprint && r.blueprint.width_px && r.blueprint.height_px) {
            const mapped = r.positions.map((p: any) => ({
              id: p.id,
              label: p.label,
              x_pct: p.blueprint_x / r.blueprint.width_px,
              y_pct: p.blueprint_y / r.blueprint.height_px,
            }));
            setRoomPositions(mapped);
          }
        }
      } catch (err) {
        console.error("Failed to load room data in Dashboard", err);
      }
    };
    loadActiveRoom();
  }, []);

  // Setup WebSocket connection
  useEffect(() => {
    // Connect to WebSocket port 8000
    const wsUrl = `ws://${window.location.hostname}:8000/ws/dashboard`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setSocketConnected(true);
      setLogs((prev) => [...prev, `[SYS] WebSocket client connected to ${wsUrl}`]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const timestamp = new Date();

        switch (data.type) {
          case "prediction": {
            const pred = data.payload as PredictionPayload;
            setPrediction(pred);
            setPredictionHistory((prev) => [pred, ...prev.slice(0, 7)]);
            
            // Add to trail history
            setTrail((prev) => {
              const updated = [...prev, { x_pct: pred.x_pct, y_pct: pred.y_pct, timestamp }];
              // Keep only last 30 seconds
              const cutOff = new Date(Date.now() - 30000);
              return updated.filter((item) => item.timestamp > cutOff);
            });
            break;
          }
          case "motion_event": {
            const motionEvent = data.payload as MotionPayload;
            setMotion((prevMotion) => {
              if (!prevMotion || prevMotion.state !== motionEvent.state) {
                if (motionEvent.state !== "NO_MOTION") {
                  setLogs((prevLogs) => [
                    ...prevLogs,
                    `[MOTION] ${motionEvent.state} (${motionEvent.direction})`
                  ]);
                }
              }
              return motionEvent;
            });
            setMotionEvents((prev) => [motionEvent, ...prev.slice(0, 15)]);
            break;
          }
          case "health": {
            const healthStats = data.payload as HealthPayload;
            setHealth(healthStats);
            break;
          }
          case "log": {
            const logEntry = data.payload as LogPayload;
            setLogs((prev) => [...prev, logEntry.message].slice(-100)); // cap logs
            break;
          }
          case "system": {
            setLogs((prev) => [...prev, `[SYS] ${data.payload.message}`]);
            break;
          }
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    ws.onclose = () => {
      setSocketConnected(false);
      setLogs((prev) => [...prev, "[SYS] WebSocket connection closed"]);
    };

    ws.onerror = () => {
      setLogs((prev) => [...prev, "[SYS] WebSocket error occurred"]);
    };

    return () => {
      ws.close();
    };
  }, []);

  // Scroll to bottom of terminal when logs update
  useEffect(() => {
    const terminal = logTerminalRef.current;
    if (terminal) {
      terminal.scrollTop = terminal.scrollHeight;
    }
  }, [logs]);

  // Draw floorplan & overlays on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, w, h);

    // 1. Draw Blueprint Image if uploaded, else draw cyber floorplan outlines
    if (blueprintImg) {
      ctx.drawImage(blueprintImg, 0, 0, w, h);
      ctx.fillStyle = "rgba(10, 10, 15, 0.35)";
      ctx.fillRect(0, 0, w, h);
    } else {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      ctx.lineWidth = 2;
      
      ctx.strokeRect(20, 20, w - 40, h - 40);

      ctx.beginPath();
      ctx.moveTo(w * 0.45, 20);
      ctx.lineTo(w * 0.45, h * 0.5);
      ctx.lineTo(20, h * 0.5);

      ctx.moveTo(w * 0.65, h - 20);
      ctx.lineTo(w * 0.65, h * 0.4);
      ctx.lineTo(w - 20, h * 0.4);
      ctx.stroke();

      ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
      ctx.font = "12px var(--font-mono)";
      ctx.fillText(activeRoom ? activeRoom.name : "MAIN ROOM", 40, h * 0.75);
    }

    // 2. Draw all configured Room Positions as 3D Person Zone Pins
    roomPositions.forEach((pos) => {
      const px = pos.x_pct * w;
      const py = pos.y_pct * h;

      // 3D Cartoon Person Pin for saved zones
      ctx.save();
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      ctx.beginPath();
      ctx.ellipse(px, py + 8, 10, 3.5, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "rgba(168, 85, 247, 0.25)";
      ctx.strokeStyle = "rgba(192, 132, 252, 0.7)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(px, py - 4, 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Cartoon Person Silhouette
      ctx.fillStyle = "#e9d5ff";
      ctx.beginPath();
      ctx.arc(px, py - 6.5, 3.2, 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(px, py + 2.5, 5.5, Math.PI * 1.15, Math.PI * 1.85);
      ctx.fill();

      ctx.fillStyle = "#d8b4fe";
      ctx.font = "bold 10px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(pos.label, px, py + 10);
      ctx.restore();
    });

    // 4. Draw Trails
    if (showTrail && trail.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = "rgba(192, 132, 252, 0.3)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);

      // Connect trail coordinates
      trail.forEach((pt, idx) => {
        const cx = pt.x_pct * w;
        const cy = pt.y_pct * h;
        if (idx === 0) {
          ctx.moveTo(cx, cy);
        } else {
          ctx.lineTo(cx, cy);
        }
      });
      ctx.stroke();
      ctx.setLineDash([]); // reset

      // Draw faint footsteps/dots along trail
      trail.forEach((pt, idx) => {
        const ageRatio = idx / trail.length; // 0 (oldest) -> 1 (newest)
        ctx.fillStyle = `rgba(192, 132, 252, ${ageRatio * 0.45})`;
        ctx.beginPath();
        ctx.arc(pt.x_pct * w, pt.y_pct * h, 3.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // 5. Draw Active Full-Body 3D Person Model Character Node
    if (prediction) {
      const x = prediction.x_pct * w;
      const y = prediction.y_pct * h;

      ctx.save();

      // 1. Realistic 3D Ground Shadow under character's feet
      ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
      ctx.beginPath();
      ctx.ellipse(x, y + 20, 22, 7, 0, 0, Math.PI * 2);
      ctx.fill();

      // 2. Outer Pulsing Hologram / Wi-Fi Radar Ring beneath character
      const auraRad = 32;
      const aura = ctx.createRadialGradient(x, y + 10, 3, x, y + 10, auraRad);
      aura.addColorStop(0, "rgba(192, 132, 252, 0.75)");
      aura.addColorStop(0.5, "rgba(168, 85, 247, 0.35)");
      aura.addColorStop(1, "rgba(168, 85, 247, 0)");
      ctx.fillStyle = aura;
      ctx.beginPath();
      ctx.ellipse(x, y + 10, auraRad, auraRad * 0.4, 0, 0, Math.PI * 2);
      ctx.fill();

      // 3. 3D Shoes / Footwear
      ctx.fillStyle = "#0f172a"; // Dark sneakers
      // Left shoe
      ctx.beginPath();
      ctx.ellipse(x - 6, y + 18, 5, 3.5, 0, 0, Math.PI * 2);
      ctx.fill();
      // Right shoe
      ctx.beginPath();
      ctx.ellipse(x + 6, y + 18, 5, 3.5, 0, 0, Math.PI * 2);
      ctx.fill();

      // White shoe soles
      ctx.fillStyle = "#f8fafc";
      ctx.fillRect(x - 10, y + 19, 8, 2);
      ctx.fillRect(x + 2, y + 19, 8, 2);

      // 4. 3D Pants / Legs
      // Left Leg
      const legGradL = ctx.createLinearGradient(x - 9, y, x - 3, y + 18);
      legGradL.addColorStop(0, "#475569");
      legGradL.addColorStop(1, "#1e293b");
      ctx.fillStyle = legGradL;
      ctx.beginPath();
      ctx.roundRect(x - 9, y, 6, 18, 3);
      ctx.fill();

      // Right Leg
      const legGradR = ctx.createLinearGradient(x + 3, y, x + 9, y + 18);
      legGradR.addColorStop(0, "#64748b");
      legGradR.addColorStop(1, "#334155");
      ctx.fillStyle = legGradR;
      ctx.beginPath();
      ctx.roundRect(x + 3, y, 6, 18, 3);
      ctx.fill();

      // 5. 3D Torso / Hoodie / Jacket
      const torsoY = y - 18;
      const torsoGrad = ctx.createLinearGradient(x - 14, torsoY, x + 14, y);
      torsoGrad.addColorStop(0, "#c084fc");
      torsoGrad.addColorStop(0.5, "#9333ea");
      torsoGrad.addColorStop(1, "#581c87");
      ctx.fillStyle = torsoGrad;
      ctx.beginPath();
      ctx.roundRect(x - 12, torsoY, 24, 20, 6);
      ctx.fill();

      // Hoodie Zipper / Jacket Accent Details
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(x, torsoY + 2);
      ctx.lineTo(x, torsoY + 20);
      ctx.stroke();

      // Inner Shirt Collar V-neck
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.moveTo(x - 4, torsoY + 2);
      ctx.lineTo(x + 4, torsoY + 2);
      ctx.lineTo(x, torsoY + 8);
      ctx.closePath();
      ctx.fill();

      // 6. 3D Arms & Hands
      // Left Arm
      ctx.fillStyle = "#7e22ce";
      ctx.beginPath();
      ctx.roundRect(x - 16, torsoY + 2, 5, 16, 2.5);
      ctx.fill();
      // Left Hand
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.arc(x - 13.5, torsoY + 18, 3, 0, Math.PI * 2);
      ctx.fill();

      // Right Arm
      ctx.fillStyle = "#a855f7";
      ctx.beginPath();
      ctx.roundRect(x + 11, torsoY + 2, 5, 16, 2.5);
      ctx.fill();
      // Right Hand
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.arc(x + 13.5, torsoY + 18, 3, 0, Math.PI * 2);
      ctx.fill();

      // 7. 3D Character Head & Face
      const headY = torsoY - 10;
      
      // Neck
      ctx.fillStyle = "#fbcfe8";
      ctx.fillRect(x - 3, headY + 5, 6, 5);

      // Face / Skin Tone (3D Sphere gradient)
      const faceGrad = ctx.createRadialGradient(x - 2, headY - 2, 2, x, headY, 9);
      faceGrad.addColorStop(0, "#fde68a");
      faceGrad.addColorStop(0.7, "#f59e0b");
      faceGrad.addColorStop(1, "#d97706");
      ctx.fillStyle = faceGrad;
      ctx.beginPath();
      ctx.arc(x, headY, 9, 0, Math.PI * 2);
      ctx.fill();

      // 3D Styled Hair
      ctx.fillStyle = "#0f172a";
      ctx.beginPath();
      ctx.arc(x, headY - 3, 9.5, Math.PI * 0.95, Math.PI * 2.05);
      ctx.fill();
      // Hair Tuft
      ctx.beginPath();
      ctx.arc(x - 2, headY - 9, 4, 0, Math.PI * 2);
      ctx.fill();

      // Cyber VR Glasses / Sunglasses
      ctx.fillStyle = "#0284c7";
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.roundRect(x - 6, headY - 2, 12, 5, 2);
      ctx.fill();
      ctx.stroke();

      // Lens Glint
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(x - 4, headY - 1, 3, 1.5);

      // 8. Floating Nameplate Tag above Character
      const confPct = Math.round(prediction.confidence * 100);
      const tagText = `🧍 ${prediction.label} (${confPct}%)`;
      ctx.font = "bold 11px Inter, system-ui, sans-serif";
      const tw = ctx.measureText(tagText).width;
      const pw = tw + 18;
      const ph = 24;
      const px = x - pw / 2;
      const py = headY - 38;

      ctx.fillStyle = "rgba(10, 10, 20, 0.94)";
      ctx.strokeStyle = "rgba(192, 132, 252, 0.9)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(px, py, pw, ph, 8);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(tagText, x, py + ph / 2);

      ctx.restore();
    }
  }, [prediction, trail, showHeatmap, showTrail, blueprintImg, roomPositions]);

  // RSSI Level descriptor
  const getRssiColor = (rssi: number) => {
    if (rssi > -60) return "text-emerald-400";
    if (rssi > -70) return "text-amber-400";
    return "text-rose-400";
  };

  const getMotionBadgeClass = (state: string) => {
    switch (state) {
      case "MOTION_STARTED":
        return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
      case "CONTINUOUS_MOTION":
        return "bg-purple-500/10 text-purple-400 border border-purple-500/20";
      case "MOTION_STOPPED":
        return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
      default:
        return "bg-gray-800 text-gray-400 border border-gray-700";
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col bg-cyber-black text-gray-300">
      {/* Glow backgrounds */}
      <div className="grid-backdrop" />
      <div className="orb orb-a" />
      <div className="orb orb-b" />

      {/* Top Header */}
      {showHeader && (
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

          <div className="flex items-center space-x-6">
            <div className="flex flex-col text-right">
              <span className="text-xs text-gray-500 font-mono uppercase tracking-wider">Active Workspace</span>
              <span className="text-sm font-semibold text-white">{activeRoom ? activeRoom.name : "Smart Apartment 4B"}</span>
            </div>

            <div className="h-8 w-px bg-white/10" />

            {/* Connection Status Badge */}
            <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-full bg-white/5 border ${socketConnected ? "border-emerald-500/30" : "border-rose-500/30"}`}>
              <span className={`w-2.5 h-2.5 rounded-full ${socketConnected ? "bg-emerald-400 pulse-glow-marker" : "bg-rose-400"}`} />
              <span className="text-xs font-mono font-bold text-white">
                {socketConnected ? "WS: CONNECTED" : "WS: DISCONNECTED"}
              </span>
            </div>
          </div>
        </header>
      )}

      {/* Main Content Layout */}
      <main className="relative z-10 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 max-w-7xl mx-auto w-full">
        
        {/* Left Column: Blueprint Canvas & Controls (2 cols span) */}
        <section className="lg:col-span-2 flex flex-col space-y-6">
          {/* Blueprint Card */}
          <div className="glow-card rounded-xl p-5 flex flex-col flex-1 min-h-[500px]">
            <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
              <div className="flex items-center space-x-2">
                <Activity className="w-5 h-5 text-neon-purple" />
                <h2 className="text-md font-semibold text-white uppercase tracking-wider font-mono">Live Blueprint Map</h2>
              </div>

              {/* Map controls */}
              <div className="flex items-center space-x-2">
                <button 
                  onClick={() => setShowHeatmap(!showHeatmap)} 
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-mono border transition ${showHeatmap ? "bg-purple-500/20 border-purple-500/40 text-purple-300" : "bg-white/5 border-white/5 text-gray-400 hover:border-white/15"}`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>HEATMAP</span>
                </button>
                <button 
                  onClick={() => setShowTrail(!showTrail)} 
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-mono border transition ${showTrail ? "bg-purple-500/20 border-purple-500/40 text-purple-300" : "bg-white/5 border-white/5 text-gray-400 hover:border-white/15"}`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>TRAIL (30s)</span>
                </button>
              </div>
            </div>

              {/* Canvas Container */}
            <div className="relative flex-1 bg-cyber-black rounded-lg border border-white/5 flex items-center justify-center overflow-hidden">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,255,255,0.015),transparent)] pointer-events-none" />
              <canvas 
                ref={canvasRef} 
                width={720} 
                height={400} 
                className="w-full h-auto aspect-[16/9] max-w-full rounded-lg"
              />

              {/* Informative placeholder when awaiting real hardware predictions */}
              {!prediction && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-cyber-black/75 backdrop-blur-xs pointer-events-none p-6 text-center z-10">
                  <div className="p-3.5 bg-purple-500/10 rounded-full border border-purple-500/20 mb-3.5">
                    <Radio className="w-8 h-8 text-neon-purple animate-pulse" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-1 tracking-tight">Awaiting Live CSI Signals & ML Model</h3>
                  <p className="text-xs text-gray-400 max-w-md mb-4 leading-relaxed">
                    Real hardware predictions will automatically render here as live packets arrive from your ESP32-CAM on UDP 5566.
                  </p>
                  <div className="flex items-center space-x-2 text-[11px] font-mono text-purple-300 bg-purple-500/10 px-3.5 py-1.5 rounded-lg border border-purple-500/20">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    <span>UDP Receiver Active on 0.0.0.0:5566</span>
                  </div>
                </div>
              )}

              {/* Dynamic reference photo of current location */}
              {prediction?.image_path && (
                <div className="absolute bottom-4 right-4 bg-cyber-gray-dark/95 border border-white/10 rounded-xl p-3.5 max-w-[220px] shadow-2xl z-10 backdrop-blur-md">
                  <div className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-2 font-bold flex items-center justify-between">
                    <span>Active Location</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-neon-purple animate-ping" />
                  </div>
                  <img 
                    src={`http://${window.location.hostname}:8000/${prediction.image_path}`} 
                    alt={prediction.label} 
                    className="w-full h-auto rounded-lg object-cover aspect-[4/3] max-h-[140px] border border-white/10"
                  />
                  <div className="mt-2.5 text-center">
                    <div className="text-xs font-mono font-bold text-white uppercase tracking-wide truncate">
                      {prediction.label}
                    </div>
                    <div className="text-[9px] text-gray-400 font-mono mt-0.5">
                      Confidence: {(prediction.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            <div className="flex justify-between items-center text-xs text-gray-500 font-mono mt-3 px-1">
              <span>* Canvas layout shows closest matching trained room zone.</span>
              <span>Grid scale: 40x40px</span>
            </div>
          </div>

          {/* Log Console Panel */}
          <div className="glow-card rounded-xl p-5 h-64 flex flex-col">
            <div className="flex items-center justify-between border-b border-white/5 pb-3 mb-3">
              <div className="flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-neon-purple" />
                <h3 className="text-sm font-semibold text-white font-mono uppercase tracking-wider">Device & Ingestion Log Console</h3>
              </div>
              <button 
                onClick={() => setLogs([])}
                className="text-xs text-gray-500 hover:text-white transition font-mono border border-white/5 hover:border-white/10 px-2 py-0.5 rounded"
              >
                CLEAR
              </button>
            </div>

            <div ref={logTerminalRef} className="flex-1 bg-[#050608] rounded-lg border border-white/5 p-3.5 overflow-y-auto font-mono text-[11px] leading-relaxed text-purple-300/80 space-y-1.5 scrollbar-thin">
              {logs.map((log, idx) => (
                <div key={idx} className="whitespace-pre-wrap select-all">
                  {log.startsWith("[SYS]") && <span className="text-cyan-400 font-bold">{log}</span>}
                  {log.startsWith("[MOTION]") && <span className="text-emerald-400">{log}</span>}
                  {!log.startsWith("[SYS]") && !log.startsWith("[MOTION]") && log}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Right Column: Metrics & Timeline Sideboard (1 col) */}
        <section className="flex flex-col space-y-6">
          {/* Signal Quality Panel */}
          <div className="glow-card rounded-xl p-5">
            <div className="flex items-center space-x-2 border-b border-white/5 pb-4 mb-4">
              <Wifi className="w-4 h-4 text-neon-purple" />
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider font-mono">Receiver Telemetry</h3>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                <span className="text-[10px] text-gray-500 font-mono uppercase block">RSSI Strength</span>
                <span className={`text-xl font-bold font-mono ${getRssiColor(health.rssi)}`}>
                  {health.rssi} <span className="text-xs font-normal text-gray-400">dBm</span>
                </span>
                <div className="w-full bg-gray-800 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div 
                    className={`h-full rounded-full ${health.rssi > -60 ? "bg-emerald-400" : health.rssi > -70 ? "bg-amber-400" : "bg-rose-400"}`}
                    style={{ width: `${Math.max(0, Math.min(100, (health.rssi + 90) * 2))}%` }}
                  />
                </div>
              </div>

              <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                <span className="text-[10px] text-gray-500 font-mono uppercase block">Packet Ingestion</span>
                <span className="text-xl font-bold font-mono text-white">
                  {health.packet_rate} <span className="text-xs font-normal text-gray-400">Hz</span>
                </span>
                <span className="text-[10px] text-emerald-400 flex items-center mt-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-ping" />
                  0.00% drops
                </span>
              </div>

              <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                <span className="text-[10px] text-gray-500 font-mono uppercase block">Motion Status</span>
                <div className="mt-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-mono uppercase font-bold inline-block ${getMotionBadgeClass(motion?.state || "NO_MOTION")}`}>
                    {motion?.state || "NO_MOTION"}
                  </span>
                </div>
                <span className="text-[9px] text-gray-500 block mt-2 font-mono truncate">
                  var: {(motion?.variance || 0.0).toFixed(4)}
                </span>
              </div>

              <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                <span className="text-[10px] text-gray-500 font-mono uppercase block">ML Inference</span>
                <span className="text-xl font-bold font-mono text-white">
                  {health.latency_ms} <span className="text-xs font-normal text-gray-400">ms</span>
                </span>
                <span className="text-[9px] text-gray-500 block mt-2 font-mono">
                  Engine: SVM
                </span>
              </div>
            </div>

            {/* Target Direction Display */}
            {motion?.state !== "NO_MOTION" && (
              <div className="mt-4 p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                <div className="flex items-center space-x-1.5">
                  <Zap className="w-3.5 h-3.5 text-neon-purple animate-bounce" />
                  <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">Dynamic Trajectory</span>
                </div>
                <p className="text-sm font-semibold text-white mt-1 capitalize leading-snug">
                  {motion?.direction}
                </p>
                <div className="text-[10px] text-purple-300 font-mono mt-1">
                  Relative speed: <span className="font-bold text-white uppercase">{motion?.speed}</span>
                </div>
              </div>
            )}
          </div>

          {/* Predictions History */}
          <div className="glow-card rounded-xl p-5 flex-1 flex flex-col">
            <div className="flex items-center space-x-2 border-b border-white/5 pb-4 mb-4">
              <History className="w-4 h-4 text-neon-purple" />
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider font-mono">Prediction Feed</h3>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 max-h-[220px] scrollbar-thin">
              {predictionHistory.length === 0 ? (
                <div className="text-xs text-gray-600 font-mono text-center py-6">
                  Awaiting WebSocket stream packets...
                </div>
              ) : (
                predictionHistory.map((item, idx) => (
                  <div key={idx} className="bg-white/5 border border-white/5 p-2.5 rounded-lg flex items-center justify-between text-xs transition hover:border-white/10">
                    <div className="flex flex-col space-y-0.5">
                      <span className="font-semibold text-white font-mono">{item.label}</span>
                      <span className="text-[10px] text-gray-500">
                        {new Date(item.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    
                    <div className="flex flex-col items-end space-y-1">
                      <span className="font-mono text-white font-bold">
                        {Math.round(item.confidence * 100)}%
                      </span>
                      <div className="w-16 bg-gray-800 h-1 rounded-full overflow-hidden">
                        <div 
                          className="bg-neon-purple h-full rounded-full" 
                          style={{ width: `${item.confidence * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Motion Event Log */}
          <div className="glow-card rounded-xl p-5 flex-1 flex flex-col">
            <div className="flex items-center space-x-2 border-b border-white/5 pb-4 mb-4">
              <Activity className="w-4 h-4 text-neon-purple" />
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider font-mono">Motion Log Timeline</h3>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 max-h-[220px] scrollbar-thin">
              {motionEvents.length === 0 ? (
                <div className="text-xs text-gray-600 font-mono text-center py-6">
                  No motion transitions logged
                </div>
              ) : (
                motionEvents.map((evt, idx) => (
                  <div key={idx} className="p-2 border-b border-white/5 flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      <span className={`w-2 h-2 rounded-full ${evt.state === "MOTION_STARTED" || evt.state === "CONTINUOUS_MOTION" ? "bg-purple-400" : evt.state === "MOTION_STOPPED" ? "bg-amber-400" : "bg-gray-700"}`} />
                      <span className="font-mono text-[11px] text-gray-400 uppercase font-semibold">
                        {evt.state.replace("MOTION_", "")}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-500 font-mono">
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

        </section>
      </main>
    </div>
  );
}
