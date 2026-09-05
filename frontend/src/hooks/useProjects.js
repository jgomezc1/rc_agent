import { useState, useEffect } from "react";
import { API_BASE_URL } from "../lib/constants";

export function useProjects() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/projects`)
      .then((res) => res.json())
      .then((data) => setProjects(data.projects || []))
      .catch(() => setProjects([]));
  }, []);

  return { projects, activeProject, setActiveProject };
}
