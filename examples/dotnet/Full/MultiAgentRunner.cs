// Multi-Agent Runner (.NET) — starts both agents for the full scenario.
// In practice, each agent runs as a separate process.
// This file documents the pattern.
using AxmeExamples;

namespace AxmeExamples.Full;

public class MultiAgentRunner
{
    public static void Main(string[] args)
    {
        Console.WriteLine("Starting agents for full/multi-agent scenario...\n");
        Console.WriteLine("In .NET, run each agent as a separate process:");
        Console.WriteLine("  AXME_API_KEY=<key1> AXME_AGENT_ADDRESS=compliance-checker-agent dotnet run --project examples/dotnet -- Delivery/StreamAgent");
        Console.WriteLine("  AXME_API_KEY=<key2> AXME_AGENT_ADDRESS=risk-assessment-agent dotnet run --project examples/dotnet -- Internal/NotificationAgent");
        Console.WriteLine("\nThen run the scenario:");
        Console.WriteLine("  axme scenarios apply examples/full/multi-agent/scenario.json --watch");
    }
}
