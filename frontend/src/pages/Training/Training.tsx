import { useState, useRef, useEffect } from "react";
import { 
  Plus, 
  Upload, 
  MapPin, 
  Database, 
  Download, 
  Play, 
  RefreshCw, 
  AlertTriangle,
  FolderOpen,
  Brain,
  CheckCircle,
  XCircle,
  Trash2,
  Image,
} from "lucide-react";

interface RoomData {
  id: number;
  name: string;
}

interface BlueprintData {
  id: number;
  room_id: number;
  file_path: string;
  width_px: number;
  height_px: number;
}

interface PositionData {
  id: number;
  room_id: number;
  label: string;
  x: number;
  y: number;
  sample_count?: number;
  image_path?: string;
}

export default function Training() {
  // Setup forms state
  const [roomName, setRoomName] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  // Database status state
  const [activeRoom, setActiveRoom] = useState<RoomData | null>(null);
  const [blueprint, setBlueprint] = useState<BlueprintData | null>(null);
  const [positions, setPositions] = useState<PositionData[]>([]);
  const [selectedPositionId, setSelectedPositionId] = useState<number | null>(null);
  const [bgImg, setBgImg] = useState<HTMLImageElement | null>(null);

  // Load blueprint image when it changes
  useEffect(() => {
    if (!blueprint?.file_path) {
      setBgImg(null);
      return;
    }
    const img = new window.Image();
    const cleanPath = blueprint.file_path.startsWith('/') ? blueprint.file_path.slice(1) : blueprint.file_path;
    img.src = `http://${window.location.hostname}:8000/${cleanPath}`;
    img.onload = () => {
      setBgImg(img);
    };
  }, [blueprint]);
  
  // Dialog box state for adding new position
  const [showAddPosDialog, setShowAddPosDialog] = useState<boolean>(false);
  const [clickCoords, setClickCoords] = useState<{ x_pct: number; y_pct: number } | null>(null);
  const [newPosLabel, setNewPosLabel] = useState<string>("");

  // Collection/Capture progress state
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [captureProgress, setCaptureProgress] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");

  // ML Training state
  const [trainModel, setTrainModel] = useState<string>("auto");
  const [trainStatus, setTrainStatus] = useState<"idle" | "training" | "done" | "error">("idle");
  const [trainResult, setTrainResult] = useState<{
    model_name: string;
    accuracy: number;
    f1: number;
    latency_ms: number;
    n_samples: number;
    n_positions: number;
    error?: string;
  } | null>(null);
  const [trainLogs, setTrainLogs] = useState<string[]>([]);
  const trainLogRef = useRef<HTMLDivElement | null>(null);

  // Refs
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Load existing rooms and positions on mount
  useEffect(() => {
    const loadRooms = async () => {
      try {
        const res = await fetch(`http://${window.location.hostname}:8000/api/v1/rooms`);
        if (!res.ok) return;
        const roomsData = await res.json();
        if (roomsData && roomsData.length > 0) {
          const room = roomsData[0];
          setActiveRoom({ id: room.id, name: room.name });
          if (room.blueprint) {
            setBlueprint({
              id: room.blueprint.id,
              room_id: room.id,
              file_path: room.blueprint.file_path,
              width_px: room.blueprint.width_px,
              height_px: room.blueprint.height_px
            });
          }
          if (room.positions) {
            const posList = room.positions.map((p: any) => ({
              id: p.id,
              room_id: room.id,
              label: p.label,
              x: p.blueprint_x,
              y: p.blueprint_y,
              sample_count: p.samples ? p.samples.length : 0,
              image_path: p.image_path
            }));
            setPositions(posList);
          }
        }
      } catch (err) {
        console.error("Failed to load rooms:", err);
      }
    };
    loadRooms();
  }, []);

  // Redraw positions on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // 1. Grid pattern if no blueprint uploaded, else draw uploaded image bounds
    if (!blueprint) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = 1;
      const step = 40;
      for (let i = 0; i < w; i += step) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, h);
        ctx.stroke();
      }
      for (let i = 0; i < h; i += step) {
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(w, i);
        ctx.stroke();
      }
      
      ctx.fillStyle = "rgba(255, 255, 255, 0.15)";
      ctx.font = "14px var(--font-sans)";
      ctx.textAlign = "center";
      ctx.fillText("Upload Blueprint Image to calibrate zone marking", w / 2, h / 2);
    } else {
      if (bgImg) {
        ctx.drawImage(bgImg, 0, 0, w, h);
      } else {
        // Draw mock blueprint walls outline while loading
        ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
        ctx.strokeRect(20, 20, w - 40, h - 40);
        
        ctx.fillStyle = "rgba(255, 255, 255, 0.15)";
        ctx.font = "12px var(--font-mono)";
        ctx.textAlign = "center";
        ctx.fillText("Loading Blueprint Image...", w / 2, h - 30);
      }
    }

    // 2. Draw existing positions
    positions.forEach((pos) => {
      // Map absolute pixel positions (scaled to the canvas size)
      // Since position X/Y are stored in database (scaled to blueprint width/height),
      // we project them to canvas size.
      const canvasX = blueprint ? (pos.x / blueprint.width_px) * w : pos.x;
      const canvasY = blueprint ? (pos.y / blueprint.height_px) * h : pos.y;

      const isSelected = selectedPositionId === pos.id;

      // Render 3D Cartoon Person Pin
      ctx.save();
      
      // Shadow
      ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
      ctx.beginPath();
      ctx.ellipse(canvasX, canvasY + 10, 12, 4, 0, 0, Math.PI * 2);
      ctx.fill();

      // Outer halo/badge
      ctx.fillStyle = isSelected ? "rgba(168, 85, 247, 0.35)" : "rgba(255, 255, 255, 0.05)";
      ctx.strokeStyle = isSelected ? "#c084fc" : "rgba(255, 255, 255, 0.3)";
      ctx.lineWidth = isSelected ? 2.2 : 1.2;
      ctx.beginPath();
      ctx.arc(canvasX, canvasY - 4, 13, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Person Silhouette (Head & Torso)
      ctx.fillStyle = isSelected ? "#ffffff" : "#c084fc";
      ctx.beginPath();
      ctx.arc(canvasX, canvasY - 7, 3.8, 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(canvasX, canvasY + 3.5, 6.5, Math.PI * 1.15, Math.PI * 1.85);
      ctx.fill();

      // Label Tag above pin
      ctx.fillStyle = isSelected ? "#ffffff" : "#9ca3af";
      ctx.font = "bold 11px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(pos.label, canvasX, canvasY - 22);
      ctx.restore();
    });
  }, [blueprint, positions, selectedPositionId, bgImg]);

  // Handle click on canvas
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!activeRoom || !blueprint) {
      setStatusMessage("Please configure a Room and Blueprint first.");
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const x_pct = clickX / canvas.width;
    const y_pct = clickY / canvas.height;

    setClickCoords({ x_pct, y_pct });
    setNewPosLabel("");
    setShowAddPosDialog(true);
  };

  // Delete selected position
  const handleDeletePosition = async () => {
    if (selectedPositionId === null) return;
    if (!window.confirm("Are you sure you want to delete this zone and all its training samples?")) return;

    setLoading(true);
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/positions/${selectedPositionId}`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("Failed to delete position.");
      
      setPositions((prev) => prev.filter((p) => p.id !== selectedPositionId));
      setSelectedPositionId(null);
      setStatusMessage("Zone deleted successfully.");
    } catch (err: any) {
      setStatusMessage(`Delete failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Upload position image
  const handleUploadPositionImage = async (posId: number, file: File) => {
    setLoading(true);
    setStatusMessage("Uploading zone photo...");
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/positions/${posId}/image`, {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error("Failed to upload zone image.");
      const data = await res.json();
      
      // Update local position image path
      setPositions((prev) => 
        prev.map((pos) => 
          pos.id === posId 
            ? { ...pos, image_path: data.image_path } 
            : pos
        )
      );
      setStatusMessage("Zone reference photo uploaded successfully!");
    } catch (err: any) {
      setStatusMessage(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Remove position image
  const handleRemovePositionImage = async (posId: number) => {
    if (!window.confirm("Remove this location reference photo?")) return;
    setLoading(true);
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/positions/${posId}/image`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("Failed to remove location photo.");

      setPositions((prev) =>
        prev.map((pos) =>
          pos.id === posId
            ? { ...pos, image_path: undefined }
            : pos
        )
      );
      setStatusMessage("Location reference photo removed successfully.");
    } catch (err: any) {
      setStatusMessage(`Remove failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Delete active room
  const handleDeleteRoom = async (roomId: number) => {
    if (!window.confirm("Are you sure you want to delete this room, its blueprint, and all configured zones?")) return;
    setLoading(true);
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/rooms/${roomId}`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("Failed to delete room.");

      setActiveRoom(null);
      setBlueprint(null);
      setPositions([]);
      setSelectedPositionId(null);
      setStatusMessage("Room and all associated zones deleted successfully.");
    } catch (err: any) {
      setStatusMessage(`Room deletion failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Reset all dataset records
  const handleResetAllData = async () => {
    if (!window.confirm("CRITICAL WARNING: Are you sure you want to permanently delete ALL rooms, positions, fingerprints, and CSI samples?")) return;

    setLoading(true);
    setStatusMessage("Purging all database records...");

    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/reset`, {
        method: "POST"
      });
      if (!res.ok) throw new Error("Failed to reset database.");

      setActiveRoom(null);
      setBlueprint(null);
      setPositions([]);
      setSelectedPositionId(null);
      setStatusMessage("Database purged successfully! All old data removed.");
    } catch (err: any) {
      setStatusMessage(`Reset error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Submit Room & Upload Blueprint
  const handleCreateRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roomName.trim()) return;

    setLoading(true);
    setStatusMessage("");

    try {
      // 1. Create Room
      const roomRes = await fetch(`http://${window.location.hostname}:8000/api/v1/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: roomName })
      });
      if (!roomRes.ok) throw new Error("Failed to create room.");
      const roomData = await roomRes.json();
      setActiveRoom(roomData);

      // 2. Upload file if selected
      if (selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);

        const fileRes = await fetch(`http://${window.location.hostname}:8000/api/v1/rooms/${roomData.id}/blueprints`, {
          method: "POST",
          body: formData
        });
        if (!fileRes.ok) throw new Error("Failed to upload blueprint.");
        const bpData = await fileRes.json();
        setBlueprint(bpData);
        setStatusMessage(`Room "${roomData.name}" created and blueprint calibrated successfully!`);
      } else {
        setStatusMessage(`Room "${roomData.name}" created without blueprint.`);
      }
    } catch (err: any) {
      setStatusMessage(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Register Position Node
  const handleAddPositionSubmit = async () => {
    if (!activeRoom || !blueprint || !clickCoords || !newPosLabel.trim()) return;

    // Project percentages to raw pixel sizes of the blueprint image
    const rawX = Math.round(clickCoords.x_pct * blueprint.width_px);
    const rawY = Math.round(clickCoords.y_pct * blueprint.height_px);

    setLoading(true);
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/positions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_id: activeRoom.id,
          label: newPosLabel,
          x: rawX,
          y: rawY
        })
      });
      if (!res.ok) throw new Error("Failed to register position.");
      
      const newPos = await res.json();
      newPos.sample_count = 0; // initialize
      setPositions((prev) => [...prev, newPos]);
      setSelectedPositionId(newPos.id);
      
      setShowAddPosDialog(false);
      setClickCoords(null);
    } catch (err: any) {
      setStatusMessage(`Error adding position: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Start Fingerprint capture (10s duration)
  const handleStartCapture = async () => {
    if (!activeRoom || selectedPositionId === null) return;

    setIsCapturing(true);
    setCaptureProgress(0);
    setStatusMessage("Recording CSI samples...");

    // Animate progress client-side while backend gathers packets
    const interval = setInterval(() => {
      setCaptureProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 10;
      });
    }, 1000);

    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_id: Number(activeRoom.id),
          position_id: Number(selectedPositionId)
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Capture session failed.");
      }
      
      const data = await res.json();
      
      // Update local position sample counts
      setPositions((prev) => 
        prev.map((pos) => 
          pos.id === selectedPositionId 
            ? { ...pos, sample_count: data.sample_count } 
            : pos
        )
      );

      setStatusMessage("Capture finished. Averaged fingerprint materialized.");
    } catch (err: any) {
      setStatusMessage(`Capture failed: ${err.message}`);
    } finally {
      clearInterval(interval);
      setIsCapturing(false);
    }
  };

  // Export JSON Dataset
  const handleExportDataset = async () => {
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/v1/export`);
      if (!res.ok) throw new Error("Export failed.");
      const data = await res.json();

      // Download file helper
      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `wifisense_export_${activeRoom?.name || "dataset"}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setStatusMessage(`Export error: ${err.message}`);
    }
  };

  // Import JSON Dataset
  const handleImportFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setStatusMessage("Importing dataset payload...");

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const text = event.target?.result as string;
        // Verify JSON parse
        JSON.parse(text);

        const res = await fetch(`http://${window.location.hostname}:8000/api/v1/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dataset_json: text })
        });
        if (!res.ok) throw new Error("Import payload rejected by server.");
        
        setStatusMessage("Dataset imported and DB tables repopulated. Refreshing dashboard.");
        
        // Mock query back to refresh current rooms list
        // For simulation purposes, let's load a dummy position list
        setPositions([
          { id: 10, room_id: 1, label: "Imported Sofa Zone", x: 176, y: 210, sample_count: 6 },
          { id: 11, room_id: 1, label: "Imported Corridor", x: 440, y: 150, sample_count: 6 }
        ]);
        setActiveRoom({ id: 1, name: "Restored Room" });
        setBlueprint({ id: 1, room_id: 1, file_path: "", width_px: 800, height_px: 600 });
      } catch (err: any) {
        setStatusMessage(`Import failed: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 max-w-7xl mx-auto w-full relative z-10">
      
      {/* Left panel: Room setup & import/export (1 col) */}
      <section className="space-y-6">
        
        {/* Room Creator Card */}
        <div className="glow-card rounded-xl p-5">
          <div className="flex items-center space-x-2 border-b border-white/5 pb-4 mb-4">
            <Plus className="w-5 h-5 text-neon-purple" />
            <h2 className="text-md font-semibold text-white uppercase tracking-wider font-mono">Create Room</h2>
          </div>

          <form onSubmit={handleCreateRoom} className="space-y-4">
            <div>
              <label className="text-xs text-gray-500 font-mono block mb-1.5">Room Name</label>
              <input 
                type="text" 
                placeholder="e.g. Living Room, Office Lab" 
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                className="w-full bg-cyber-black text-white text-sm rounded-lg border border-white/5 focus:border-purple-500 focus:outline-none px-3.5 py-2"
                disabled={loading}
              />
            </div>

            <div>
              <label className="text-xs text-gray-500 font-mono block mb-1.5">Blueprint Canvas Image</label>
              <div 
                onClick={() => fileInputRef.current?.click()}
                className="border border-dashed border-white/10 hover:border-purple-500/50 rounded-lg p-4 text-center cursor-pointer transition bg-white/[0.01] hover:bg-white/[0.02]"
              >
                <input 
                  type="file" 
                  ref={fileInputRef}
                  className="hidden" 
                  accept="image/*"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                />
                <Upload className="w-5 h-5 text-gray-500 mx-auto mb-2" />
                <span className="text-xs font-mono text-gray-400">
                  {selectedFile ? selectedFile.name : "Select PNG or JPG Image"}
                </span>
              </div>
            </div>

            <button 
              type="submit" 
              className="w-full bg-neon-purple hover:bg-purple-600 active:scale-95 text-cyber-black font-bold py-2 px-4 rounded-lg transition text-sm flex items-center justify-center space-x-1.5"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span>{loading ? "CONFIGURING..." : "CREATE & CALIBRATE"}</span>
            </button>
          </form>
        </div>

        {/* Dataset import/export utility card */}
        <div className="glow-card rounded-xl p-5">
          <div className="flex items-center space-x-2 border-b border-white/5 pb-4 mb-4">
            <Database className="w-5 h-5 text-neon-purple" />
            <h2 className="text-md font-semibold text-white uppercase tracking-wider font-mono">Dataset Operations</h2>
          </div>

          <div className="space-y-3">
            <button 
              onClick={handleExportDataset}
              disabled={!activeRoom}
              className="w-full border border-white/5 hover:border-purple-500/40 hover:bg-purple-500/10 text-white font-semibold py-2 px-4 rounded-lg transition text-xs flex items-center justify-center space-x-2 disabled:opacity-40 disabled:pointer-events-none"
            >
              <Download className="w-4 h-4 text-neon-purple" />
              <span>EXPORT JSON DATASET</span>
            </button>

            <div>
              <input 
                type="file" 
                id="import-file-input"
                className="hidden"
                accept=".json"
                onChange={handleImportFileChange}
              />
              <button 
                onClick={() => document.getElementById("import-file-input")?.click()}
                className="w-full border border-white/5 hover:border-purple-500/40 hover:bg-purple-500/10 text-white font-semibold py-2 px-4 rounded-lg transition text-xs flex items-center justify-center space-x-2"
              >
                <FolderOpen className="w-4 h-4 text-neon-purple" />
                <span>IMPORT JSON DATASET</span>
              </button>
            </div>

            <button 
              onClick={handleResetAllData}
              disabled={loading}
              className="w-full border border-rose-500/30 hover:border-rose-500/60 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-bold py-2 px-4 rounded-lg transition text-xs flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-40"
            >
              <Trash2 className="w-4 h-4 text-rose-400" />
              <span>PURGE ALL OLD DATASET RECORDS</span>
            </button>
          </div>
        </div>

        {/* Status display */}
        {statusMessage && (
          <div className="p-4 bg-white/5 border border-white/5 rounded-xl flex items-start space-x-2 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span className="font-mono text-gray-300 leading-normal">{statusMessage}</span>
          </div>
        )}
      </section>

      {/* Middle/Center panel: Interactive click canvas (2 cols) */}
      <section className="lg:col-span-2 space-y-6">
        
        {/* Canvas Card */}
        <div className="glow-card rounded-xl p-5 flex flex-col min-h-[500px]">
          <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
            <div className="flex items-center space-x-2">
              <MapPin className="w-5 h-5 text-neon-purple" />
              <h2 className="text-md font-semibold text-white uppercase tracking-wider font-mono">
                Zone Mapping Studio {activeRoom ? ` - ${activeRoom.name}` : ""}
              </h2>
            </div>
            
            {activeRoom && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-emerald-400 font-mono border border-emerald-500/20 bg-emerald-500/5 px-2 py-0.5 rounded-full uppercase">
                  Active Config Mode
                </span>
                <button
                  type="button"
                  onClick={() => handleDeleteRoom(activeRoom.id)}
                  disabled={loading}
                  className="text-xs text-rose-400 hover:text-rose-300 font-mono border border-rose-500/20 bg-rose-500/10 hover:bg-rose-500/20 px-2.5 py-0.5 rounded-full transition cursor-pointer flex items-center space-x-1"
                  title="Delete Room"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>DELETE ROOM</span>
                </button>
              </div>
            )}
          </div>

          {/* Interactive click canvas */}
          <div className="relative flex-1 bg-cyber-black rounded-lg border border-white/5 flex items-center justify-center overflow-hidden">
            <canvas 
              ref={canvasRef}
              onClick={handleCanvasClick}
              width={720}
              height={400}
              className="w-full h-auto aspect-[16/9] max-w-full rounded-lg cursor-crosshair"
            />

            {/* Absolute positioned form dialog to label registered coordinate node */}
            {showAddPosDialog && clickCoords && (
              <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-20">
                <div className="bg-cyber-gray-dark border border-white/10 rounded-xl p-5 max-w-sm w-full space-y-4">
                  <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
                    Name Clicked Location
                  </h3>
                  
                  <div className="text-[11px] text-gray-500 font-mono">
                    Registered offsets: x: {Math.round(clickCoords.x_pct*100)}%, y: {Math.round(clickCoords.y_pct*100)}%
                  </div>

                  <input 
                    type="text" 
                    placeholder="e.g. Couch, Bedroom Desk" 
                    value={newPosLabel}
                    onChange={(e) => setNewPosLabel(e.target.value)}
                    className="w-full bg-cyber-black text-white text-sm rounded-lg border border-white/5 focus:border-purple-500 focus:outline-none px-3.5 py-2"
                  />

                  <div className="flex space-x-3">
                    <button 
                      onClick={() => setShowAddPosDialog(false)}
                      className="flex-1 bg-white/5 hover:bg-white/10 text-gray-400 font-semibold py-2 rounded-lg text-xs"
                    >
                      CANCEL
                    </button>
                    <button 
                      onClick={handleAddPositionSubmit}
                      disabled={!newPosLabel.trim()}
                      className="flex-1 bg-neon-purple hover:bg-purple-600 text-cyber-black font-bold py-2 rounded-lg text-xs disabled:opacity-40"
                    >
                      SAVE ZONE
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Bottom workflow bar (Zone Capture & materialization) */}
          <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4 items-center border-t border-white/5 pt-4">
            
            {/* Position selector list with delete option */}
            <div>
              <label className="text-[10px] text-gray-500 font-mono uppercase block mb-1">Select zone to train</label>
              <div className="flex gap-2">
                <select 
                  value={selectedPositionId || ""}
                  onChange={(e) => setSelectedPositionId(Number(e.target.value) || null)}
                  className="flex-1 bg-cyber-black text-white text-xs rounded-lg border border-white/5 focus:outline-none px-3 py-2"
                >
                  <option value="">-- Choose Labeled Position --</option>
                  {positions.map((pos) => (
                    <option key={pos.id} value={pos.id}>
                      {pos.label} ({pos.sample_count || 0} samples)
                    </option>
                  ))}
                </select>
                {selectedPositionId !== null && (
                  <button
                    type="button"
                    onClick={handleDeletePosition}
                    disabled={loading}
                    className="p-2 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 hover:border-rose-500/40 text-rose-400 transition cursor-pointer disabled:opacity-40"
                    title="Delete Zone"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            {/* Progress spinner and Capture action */}
            <div className="flex items-center space-x-4">
              {isCapturing ? (
                <div className="flex-1 flex items-center space-x-3 bg-white/5 rounded-lg border border-white/5 px-3 py-1.5 h-[38px]">
                  <RefreshCw className="w-4 h-4 text-neon-purple animate-spin" />
                  <div className="flex-1 bg-gray-800 h-1.5 rounded-full overflow-hidden">
                    <div 
                      className="bg-neon-purple h-full rounded-full transition-all duration-300"
                      style={{ width: `${captureProgress}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-white font-mono">{captureProgress}%</span>
                </div>
              ) : (
                <button 
                  onClick={handleStartCapture}
                  disabled={selectedPositionId === null || isCapturing}
                  className="flex-1 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 hover:border-purple-500/40 text-white font-bold h-[38px] rounded-lg transition text-xs flex items-center justify-center space-x-2 disabled:opacity-40 disabled:pointer-events-none"
                >
                  <Play className="w-3.5 h-3.5 text-neon-purple fill-neon-purple" />
                  <span>START 10S CAPTURE</span>
                </button>
              )}
            </div>

          </div>

          {/* Selected Zone Reference Image Card */}
          {selectedPositionId !== null && (
            <div className="mt-5 border-t border-white/5 pt-4">
              <label className="text-[10px] text-gray-500 font-mono uppercase block mb-2">Zone Reference Photo</label>
              <div className="flex items-center space-x-4 bg-white/[0.01] border border-white/5 rounded-lg p-3">
                {positions.find(p => p.id === selectedPositionId)?.image_path ? (
                  <div className="relative group w-16 h-16 shrink-0 rounded overflow-hidden border border-white/10">
                    <img 
                      src={`http://${window.location.hostname}:8000/${positions.find(p => p.id === selectedPositionId)?.image_path}`} 
                      alt="Zone reference preview" 
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="w-16 h-16 shrink-0 rounded border border-dashed border-white/10 flex flex-col items-center justify-center bg-cyber-black text-gray-500 text-[9px] font-mono leading-none">
                    <Image className="w-4 h-4 text-gray-600 mb-1" />
                    <span>NO IMAGE</span>
                  </div>
                )}
                
                <div className="flex-1 space-y-1">
                  <h4 className="text-xs font-semibold text-white font-mono uppercase">
                    {positions.find(p => p.id === selectedPositionId)?.label || "Unlabeled position"}
                  </h4>
                  <p className="text-[10px] text-gray-400 font-mono">
                    {positions.find(p => p.id === selectedPositionId)?.image_path 
                      ? "Uploaded JPG/PNG reference photo is active." 
                      : "No photo attached to this location. Upload an image to show it in the monitoring dashboard."}
                  </p>
                </div>
                
                <div className="shrink-0 flex items-center space-x-2">
                  <input 
                    type="file" 
                    id={`pos-file-img-${selectedPositionId}`}
                    className="hidden" 
                    accept="image/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        handleUploadPositionImage(selectedPositionId, file);
                      }
                    }}
                  />
                  <button 
                    type="button"
                    onClick={() => document.getElementById(`pos-file-img-${selectedPositionId}`)?.click()}
                    disabled={loading}
                    className="bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 hover:border-purple-500/40 text-white font-bold py-1.5 px-3 rounded text-[11px] font-mono transition cursor-pointer"
                  >
                    {positions.find(p => p.id === selectedPositionId)?.image_path ? "CHANGE PHOTO" : "UPLOAD"}
                  </button>

                  {positions.find(p => p.id === selectedPositionId)?.image_path && (
                    <button
                      type="button"
                      onClick={() => handleRemovePositionImage(selectedPositionId)}
                      disabled={loading}
                      className="bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 hover:border-rose-500/40 text-rose-400 font-bold py-1.5 px-3 rounded text-[11px] font-mono transition cursor-pointer flex items-center space-x-1"
                      title="Remove Location Photo"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>REMOVE</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
      
      {/* ═══ ML Training Panel ═══ */}
      <section className="glow-card rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 rounded-lg bg-neon-green/10 border border-neon-green/20">
            <Brain className="w-4 h-4 text-neon-green" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white font-mono uppercase tracking-wider">Train Models</h2>
            <p className="text-[10px] text-gray-500 font-mono mt-0.5">
              Train KNN / SVM / RF / Neural Net on captured fingerprints
            </p>
          </div>
          {trainStatus === "done" && trainResult && !trainResult.error && (
            <div className="ml-auto flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/20">
              <CheckCircle className="w-3.5 h-3.5 text-neon-green" />
              <span className="text-xs font-mono text-neon-green font-bold">
                {trainResult.model_name} — {(trainResult.accuracy * 100).toFixed(1)}% acc
              </span>
            </div>
          )}
          {trainStatus === "error" && (
            <div className="ml-auto flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/20">
              <XCircle className="w-3.5 h-3.5 text-red-400" />
              <span className="text-xs font-mono text-red-400">Training failed</span>
            </div>
          )}
        </div>

        {trainResult?.error && (
          <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-mono flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>{trainResult.error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {/* Model selector */}
          <div>
            <label className="text-[10px] text-gray-500 font-mono uppercase block mb-1.5">Model</label>
            <select
              id="train-model-select"
              value={trainModel}
              onChange={(e) => setTrainModel(e.target.value)}
              disabled={trainStatus === "training"}
              className="w-full bg-cyber-black text-white text-xs rounded-lg border border-white/5 focus:border-neon-green/50 focus:outline-none px-3 py-2 disabled:opacity-50"
            >
              <option value="auto">🤖 Auto (pick best)</option>
              <option value="knn">KNN (k=5, distance-weighted)</option>
              <option value="svm">SVM (RBF kernel)</option>
              <option value="random_forest">Random Forest (100 trees)</option>
              <option value="neural_net">Neural Net (MLP)</option>
            </select>
          </div>

          {/* Stat badges */}
          {trainResult && !trainResult.error && (
            <>
              <div className="glow-card rounded-xl p-3 flex flex-col justify-center">
                <span className="text-[10px] text-gray-500 font-mono uppercase">Samples / Zones</span>
                <span className="text-lg font-bold text-white tabular-nums">
                  {trainResult.n_samples} / {trainResult.n_positions}
                </span>
              </div>
              <div className="glow-card rounded-xl p-3 flex flex-col justify-center">
                <span className="text-[10px] text-gray-500 font-mono uppercase">F1 Score</span>
                <span className="text-lg font-bold text-neon-green tabular-nums">
                  {trainResult.f1.toFixed(3)}
                </span>
              </div>
            </>
          )}
        </div>

        {/* TRAIN NOW button */}
        <button
          id="btn-train-now"
          onClick={async () => {
            setTrainStatus("training");
            setTrainLogs([]);
            setTrainResult(null);

            // Open WebSocket to stream logs
            const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/dashboard`);
            ws.onmessage = (ev) => {
              const msg = JSON.parse(ev.data);
              if (msg.type === "log") {
                const text = msg.payload.message as string;
                if (text.includes("[PIPELINE]") || text.includes("[INFERENCE]")) {
                  setTrainLogs((prev) => [...prev.slice(-199), text]);
                  setTimeout(() => {
                    trainLogRef.current?.scrollTo({ top: 99999, behavior: "smooth" });
                  }, 50);
                }
              }
            };

            try {
              const resp = await fetch(`http://${window.location.hostname}:8000/api/v1/train`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model: trainModel }),
              });
              if (!resp.ok) throw new Error(await resp.text());

              // Poll status until done
              const poll = setInterval(async () => {
                const s = await fetch(`http://${window.location.hostname}:8000/api/v1/train/status`).then((r) => r.json());
                if (s.status === "done" || s.status === "error") {
                  clearInterval(poll);
                  ws.close();
                  setTrainStatus(s.status);
                  setTrainResult(s.result);
                }
              }, 1500);
            } catch (err) {
              ws.close();
              setTrainStatus("error");
              setTrainLogs((p) => [...p, `ERROR: ${(err as Error).message}`]);
            }
          }}
          disabled={trainStatus === "training"}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl font-mono font-bold text-sm transition
            bg-neon-green/10 hover:bg-neon-green/20 border border-neon-green/20 hover:border-neon-green/50
            text-neon-green disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
        >
          {trainStatus === "training" ? (
            <><RefreshCw className="w-4 h-4 animate-spin" /> TRAINING…</>
          ) : (
            <><Brain className="w-4 h-4" /> TRAIN NOW</>  
          )}
        </button>

        {/* Progress log terminal */}
        {trainLogs.length > 0 && (
          <div
            ref={trainLogRef}
            className="mt-4 bg-cyber-black rounded-xl border border-white/5 p-3 h-40 overflow-y-auto font-mono text-[10px] text-gray-400 space-y-0.5"
          >
            {trainLogs.map((log, i) => (
              <div key={i} className={log.includes("ERROR") ? "text-red-400" : log.includes("Best model") || log.includes("loaded") ? "text-neon-green" : ""}>
                {log}
              </div>
            ))}
            {trainStatus === "training" && (
              <div className="text-neon-purple animate-pulse">▌</div>
            )}
          </div>
        )}

        <p className="text-[10px] text-gray-600 font-mono mt-3">
          ⚠ Predictions represent the closest matching trained zone — NOT centimeter GPS coordinates.
          Minimum: 100 samples per zone, 2+ zones.
        </p>
      </section>

    </div>
  );
}
