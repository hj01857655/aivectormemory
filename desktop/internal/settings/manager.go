package settings

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

type Settings struct {
	Theme       string `json:"theme"`        // dark, light, system
	Language    string `json:"language"`      // zh-CN, en, ...
	DBPath      string `json:"db_path"`       // custom db path
	PythonPath  string `json:"python_path"`   // custom python path
	WebPort     int    `json:"web_port"`      // web dashboard port
	AutoStart   bool   `json:"auto_start"`    // launch at login
	LastProject string `json:"last_project"`  // last opened project
	WindowWidth  int   `json:"window_width"`
	WindowHeight int   `json:"window_height"`
	WindowX      int   `json:"window_x"`
	WindowY      int   `json:"window_y"`
}

func DefaultSettings() *Settings {
	return &Settings{
		Theme:        "dark",
		Language:     "zh-CN",
		DBPath:       defaultDBPath(),
		PythonPath:   "",
		WebPort:      9080,
		AutoStart:    false,
		LastProject:  "",
		WindowWidth:  1200,
		WindowHeight: 800,
		WindowX:      -1,
		WindowY:      -1,
	}
}

func configPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".aivectormemory", "desktop.json")
}

func defaultDBPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".aivectormemory", "memory.db")
}

func Load() *Settings {
	s := DefaultSettings()
	data, err := os.ReadFile(configPath())
	if err != nil {
		return s
	}
	json.Unmarshal(data, s)

	// Expand ~ in paths
	if strings.HasPrefix(s.DBPath, "~") {
		home, _ := os.UserHomeDir()
		s.DBPath = filepath.Join(home, s.DBPath[1:])
	}

	// Apply defaults for zero values
	if s.WebPort == 0 {
		s.WebPort = 9080
	}
	if s.Language == "" {
		s.Language = "zh-CN"
	}
	if s.Theme == "" {
		s.Theme = "dark"
	}
	if s.WindowWidth == 0 {
		s.WindowWidth = 1200
	}
	if s.WindowHeight == 0 {
		s.WindowHeight = 800
	}

	return s
}

func Save(s *Settings) error {
	dir := filepath.Dir(configPath())
	os.MkdirAll(dir, 0755)

	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(configPath(), data, 0644)
}
