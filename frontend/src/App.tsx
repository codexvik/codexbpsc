import { BrowserRouter, Route, Routes } from "react-router-dom";
import Header from "./components/Header";
import ExamDetail from "./pages/ExamDetail";
import Home from "./pages/Home";
import Saved from "./pages/Saved";

export default function App() {
  return (
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/exams/:id" element={<ExamDetail />} />
        <Route path="/saved" element={<Saved />} />
      </Routes>
      <div style={{ borderTop: "1px solid var(--color-border-neutral)", padding: "22px 16px", textAlign: "center", fontSize: 11.5, color: "var(--color-text-muted)" }}>
        SarkariExams · Starting in Bihar, built for every state
      </div>
    </BrowserRouter>
  );
}
