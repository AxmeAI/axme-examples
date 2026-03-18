// Run both agents for the full multi-agent scenario (Go).
//
// Usage:
//
//	go run examples/full/multi-agent/run_agents.go
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
)

type agentSpec struct {
	nameFragment string
	script       string
	address      string
}

func loadAPIKey(nameFragment string) string {
	home, _ := os.UserHomeDir()
	data, err := os.ReadFile(filepath.Join(home, ".config", "axme", "scenario-agents.json"))
	if err != nil { return "" }
	var raw map[string]any
	json.Unmarshal(data, &raw)
	agents, _ := raw["agents"].([]any)
	for _, a := range agents {
		m, _ := a.(map[string]any)
		addr, _ := m["address"].(string)
		key, _ := m["api_key"].(string)
		if len(addr) > 0 && len(key) > 0 {
			if contains(addr, nameFragment) { return key }
		}
	}
	return ""
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 || findSubstring(s, sub))
}
func findSubstring(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub { return true }
	}
	return false
}

func main() {
	_, thisFile, _, _ := runtime.Caller(0)
	workspace := filepath.Join(filepath.Dir(thisFile), "..", "..", "..")

	agents := []agentSpec{
		{"compliance-checker", filepath.Join(workspace, "examples", "delivery", "stream", "agent.go"), "compliance-checker-agent"},
		{"risk-assessment", filepath.Join(workspace, "examples", "internal", "notification", "agent.go"), "risk-assessment-agent"},
	}

	fmt.Println("Starting agents for full/multi-agent scenario...")
	fmt.Println()

	var procs []*exec.Cmd
	for _, a := range agents {
		key := loadAPIKey(a.nameFragment)
		if key == "" { key = os.Getenv("AXME_API_KEY") }
		if key == "" { fmt.Fprintf(os.Stderr, "[warn] no API key for '%s'\n", a.nameFragment) }

		env := append(os.Environ(), "AXME_AGENT_ADDRESS="+a.address)
		if key != "" { env = append(env, "AXME_API_KEY="+key) }

		fmt.Printf("[agent]  %s — %s\n", a.address, filepath.Base(a.script))
		cmd := exec.Command("go", "run", a.script)
		cmd.Env = env
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		cmd.Start()
		procs = append(procs, cmd)
	}

	fmt.Println("\nBoth agents running. Press Ctrl+C to stop.")

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	<-c

	fmt.Println("\nShutting down agents...")
	for _, p := range procs {
		if p.Process != nil { p.Process.Kill() }
	}
}
