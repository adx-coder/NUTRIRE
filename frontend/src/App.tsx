import { Routes, Route, Navigate } from "react-router-dom";
import Home from "@/pages/Home";
import Sandbox from "@/pages/Sandbox";
import BestMatch from "@/pages/BestMatch";
import OrgDetail from "@/pages/OrgDetail";
import AllOptions from "@/pages/AllOptions";
import GiveHome from "@/pages/GiveHome";
import Donate from "@/pages/Donate";
import Volunteer from "@/pages/Volunteer";
import MapPage from "@/pages/Map";
import Recommendations from "@/pages/Recommendations";
import Methodology from "@/pages/Methodology";

export default function App() {
  return (
    <Routes>
      {/* Maria linear flow */}
      <Route path="/" element={<Home />} />
      <Route path="/find" element={<BestMatch />} />
      <Route path="/org/:id" element={<OrgDetail />} />
      <Route path="/all" element={<AllOptions />} />

      {/* Helper door */}
      <Route path="/give" element={<GiveHome />} />
      <Route path="/give/donate" element={<Donate />} />
      <Route path="/give/volunteer" element={<Volunteer />} />

      {/* Research door */}
      <Route path="/map" element={<MapPage />} />
      <Route path="/recommendations" element={<Recommendations />} />
      <Route path="/methodology" element={<Methodology />} />

      {/* Dev */}
      <Route path="/sandbox" element={<Sandbox />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
