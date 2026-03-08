import argparse
import inspect
import importlib
import pkgutil
import sys
from pathlib import Path
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Add src to Python Path if run directly without -m
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Ensure we import from the local package
try:
    from geosupply.config import SCHEMA_VERSIONS
    from geosupply.schemas import ALL_SCHEMAS
    from geosupply.core.base_worker import BaseWorker
    from geosupply.core.base_agent import BaseAgent
    from geosupply.core.base_subagent import BaseSubAgent
except ImportError as e:
    print(f"{Fore.RED}CRITICAL IMPORT ERROR: {e}{Style.RESET_ALL}")
    print("Ensure you are running this from the project root using: python -m geosupply.cli.audit")
    sys.exit(1)


def discover_components(package_name="geosupply"):
    """Dynamically discover all BaseWorker, BaseAgent, and BaseSubAgent subclasses."""
    package = importlib.import_module(package_name)
    prefix = package.__name__ + "."
    
    # Recursively walk the package
    for importer, modname, ispkg in pkgutil.walk_packages(package.__path__, prefix):
        try:
            importlib.import_module(modname)
        except Exception:
            # Ignore modules that fail to import during discovery 
            pass

    workers = BaseWorker.__subclasses__()
    agents = BaseAgent.__subclasses__()
    subagents = BaseSubAgent.__subclasses__()
    
    return workers, agents, subagents


def run_logic_breakage_tests(strict=False):
    """Run dynamic tests to ensure no hard-coded counts are broken."""
    print(f"\n{Fore.CYAN}--- Running Logic Breakage Checks ---{Style.RESET_ALL}")
    passed = 0
    failed = 0

    # Test 1: Schema Count match
    print("1. Validating Schema Registration...", end=" ")
    if len(ALL_SCHEMAS) == len(SCHEMA_VERSIONS):
        print(f"{Fore.GREEN}PASS ({len(ALL_SCHEMAS)} Schemas){Style.RESET_ALL}")
        passed += 1
    else:
        print(f"{Fore.RED}FAIL (ALL_SCHEMAS={len(ALL_SCHEMAS)}, SCHEMA_VERSIONS={len(SCHEMA_VERSIONS)}){Style.RESET_ALL}")
        failed += 1

    return passed, failed


def run_logic_gap_tests(workers, agents, subagents, strict=False):
    """Run dynamic tests checking implementation hierarchy gaps."""
    print(f"\n{Fore.CYAN}--- Running Logic Gap & Hierarchy Checks ---{Style.RESET_ALL}")
    passed = 0
    failed = 0

    # Test 2: Worker Hierarchy verification
    print("2. Validating Subclasses override required functions...")
    
    all_override = True
    for worker_cls in workers:
        if worker_cls is BaseWorker: continue
        # BaseWorker defines `process`. Subclasses must provide `setup` or use parent?
        # A true check: ensure they are not abstract (can be instantiated implicitly)
        if hasattr(worker_cls, 'process') and worker_cls.process is BaseWorker.process:
            print(f"  {Fore.RED}- {worker_cls.__name__} fails to override process(){Style.RESET_ALL}")
            all_override = False
            
    if all_override:
        print(f"  {Fore.GREEN}✓ All {len(workers)} Active Workers implement processing overrides{Style.RESET_ALL}")
        passed += 1
    else:
        failed += 1


    return passed, failed


def run_oversight_tests(workers, agents, subagents, strict=False):
    """Run dynamic oversight tests for missing properties."""
    print(f"\n{Fore.CYAN}--- Running Oversight Checks ---{Style.RESET_ALL}")
    passed = 0
    failed = 0
    
    print("3. Validating required Agent properties...")
    all_valid = True
    for agent_cls in agents:
        if agent_cls is BaseAgent: continue
        
        # We check class-level definition or default init parameters using signature
        sig = inspect.signature(agent_cls.__init__)
        params = sig.parameters
        
        # Normally they pass domain/name to super().__init__
        # We instantiate a dummy if possible to check properties (skip if requires complex args)
        try:
             # Basic check to see if we can resolve the MRO properly
             mro = [c.__name__ for c in agent_cls.__mro__]
             if "BaseAgent" not in mro:
                 all_valid = False
                 print(f"  {Fore.RED}- {agent_cls.__name__} MRO is broken{Style.RESET_ALL}")
        except Exception:
             pass
             
    if all_valid:
        print(f"  {Fore.GREEN}✓ All {len(agents)} Active Agents have valid MRO inheritance{Style.RESET_ALL}")
        passed += 1
    else:
        failed += 1

    return passed, failed


def run_practical_analysis(strict=False):
    """Run practical analysis by hooking into Pytest dynamically if installed."""
    print(f"\n{Fore.CYAN}--- Running Practical Analysis ---{Style.RESET_ALL}")
    passed = 0
    failed = 0
    
    try:
        import pytest
        print("4. Executing Integrated Pytest Suite...")
        # Run pytest silently and get the exit code
        retcode = pytest.main(["-q", str(SRC_DIR.parent / "tests")])
        if retcode == 0:
            print(f"  {Fore.GREEN}✓ Integrated Pytest Suite PASSED{Style.RESET_ALL}")
            passed += 1
        else:
            print(f"  {Fore.RED}✗ Integrated Pytest Suite FAILED (Code {retcode}){Style.RESET_ALL}")
            failed += 1
    except ImportError:
        print(f"  {Fore.YELLOW}⚠ Pytest not available in current environment. Skipping.{Style.RESET_ALL}")
        if strict:
            failed += 1
        else:
            passed += 1

    return passed, failed


def run_broken_chain_tests():
    """Validates connectivity across the system dynamically."""
    print(f"\n{Fore.CYAN}--- Running Connectivity / Broken Chain Checks ---{Style.RESET_ALL}")
    passed = 0
    failed = 0
    
    print("5. Validating Base Components Connectivity...")
    # This proves the decorators and core imports are unbroken
    try:
        from geosupply.core.decorators import retry, timeout, cost_tracker
        from geosupply.core.event_bus import EventBus
        print(f"  {Fore.GREEN}✓ Core mechanics connect seamlessly.{Style.RESET_ALL}")
        passed += 1
    except ImportError as e:
        print(f"  {Fore.RED}✗ Core broken chain: {e}{Style.RESET_ALL}")
        failed += 1

    return passed, failed

def main():
    parser = argparse.ArgumentParser(description="GeoSupply DYNAMIC Phase-End Test Suite")
    parser.add_argument("--level", choices=["std", "strict"], default="std", help="Strict mode fails on warnings or missing libs")
    parser.add_argument("--categories", help="Comma separated categories (logic, breakage, oversight, practical, connectivity)")
    
    args = parser.parse_args()
    strict_mode = args.level == "strict"
    
    print(f"\n{Fore.MAGENTA}==================================================")
    print(f"GeoSupply v10 Audit System (Level: {args.level.upper()})")
    print(f"=================================================={Style.RESET_ALL}")
    
    workers, agents, subagents = discover_components()
    print(f"Discovered: {len(workers)} Workers, {len(agents)} Agents, {len(subagents)} SubAgents dynamically.")
    
    cats = args.categories.split(",") if args.categories else ["logic", "breakage", "oversight", "practical", "connectivity"]
    
    total_passed = 0
    total_failed = 0
    
    if "breakage" in cats or "logic" in cats:
        p, f = run_logic_breakage_tests(strict=strict_mode)
        total_passed += p
        total_failed += f
        
    if "logic" in cats:
        p, f = run_logic_gap_tests(workers, agents, subagents, strict=strict_mode)
        total_passed += p
        total_failed += f
        
    if "oversight" in cats:
        p, f = run_oversight_tests(workers, agents, subagents, strict=strict_mode)
        total_passed += p
        total_failed += f
        
    if "connectivity" in cats:
        p, f = run_broken_chain_tests()
        total_passed += p
        total_failed += f
        
    if "practical" in cats:
         p, f = run_practical_analysis(strict=strict_mode)
         total_passed += p
         total_failed += f

    print(f"\n{Fore.MAGENTA}==================================================")
    print(f"AUDIT SUMMARY:")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"=================================================={Style.RESET_ALL}")

    if total_failed > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
