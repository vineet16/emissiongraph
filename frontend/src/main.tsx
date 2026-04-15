import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import FleetDashboard from "./pages/FleetDashboard";
import PortDetail from "./pages/PortDetail";
import Comparison from "./pages/Comparison";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<FleetDashboard />} />
        <Route path="/port/:portId" element={<PortDetail />} />
        <Route path="/compare/:portA/:portB" element={<Comparison />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
