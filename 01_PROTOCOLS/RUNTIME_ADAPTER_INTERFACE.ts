/**
 * RuntimeAdapter Interface
 *
 * All runtime executors (roach-pi, LangGraph, OpenHands, etc.) must implement this interface
 * to be compatible with the Chromatic Harness governance and observability layer.
 */

/**
 * Mission Packet: Input to any runtime
 * Defined in MISSION_PACKET_SCHEMA.json
 */
export interface MissionPacket {
  mission_id: string;
  intent: string;
  agent_framework: 'roach-pi' | 'langraph' | 'openhands' | string;
  scope: string[];
  budget: {
    tokens: number;
    tool_calls: number;
  };
  required_gates: ('intent' | 'scope' | 'confidence')[];
  sandbox_level?: 0 | 1 | 2 | 3 | 4 | 5; // L0-L5 for external agents; omit for trusted runtimes
  metadata?: Record<string, any>;
}

/**
 * Execution result from runtime: what actually happened
 */
export interface ExecutionResult {
  mission_id: string;
  status: 'success' | 'partial' | 'failed';

  // What the runtime produced
  output: {
    closed_tasks: Task[];
    blocked_tasks: Task[];
    created_artifacts: Artifact[];
  };

  // Observable telemetry
  telemetry: {
    tokens_used: number;
    tool_calls_count: number;
    tool_calls: ToolCall[];
    errors: ExecutionError[];
    retries: number;
    duration_ms: number;
    test_results?: TestResult[];
  };

  // What the agent learned
  learnings: Learning[];

  // Magnet reports from runtime observation
  magnet_reports: MagnetReport[];
}

/**
 * Task completion tracking
 */
export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'completed' | 'blocked' | 'in_progress';
  blocked_on?: string; // What's blocking this task
  evidence?: Record<string, any>; // Tests passed, PR merged, etc.
}

/**
 * An artifact created during execution (file, PR, etc.)
 */
export interface Artifact {
  type: 'file' | 'commit' | 'pr' | 'branch' | 'test_result' | string;
  name: string;
  path?: string;
  url?: string;
  content?: string;
  metadata?: Record<string, any>;
}

/**
 * Tool invocation observed by magnets
 */
export interface ToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  result: any;
  duration_ms: number;
  timestamp: number;
  error?: string;
  retry_count: number;
}

/**
 * An error that occurred during execution
 */
export interface ExecutionError {
  code: string;
  message: string;
  stage: 'init' | 'planning' | 'execution' | 'validation' | 'review';
  recoverable: boolean;
  tool_call?: ToolCall;
  timestamp: number;
}

/**
 * Test result from runtime validation
 */
export interface TestResult {
  test_name: string;
  status: 'pass' | 'fail' | 'skip';
  duration_ms: number;
  assertion?: string;
  error_message?: string;
}

/**
 * Learning extracted from execution
 */
export interface Learning {
  title: string;
  detail: string;
  tags: string[];
  confidence: number; // 0-1
  applicable_to?: string[]; // What future tasks this applies to
}

/**
 * Magnet observability report (see Magnets Integration)
 */
export interface MagnetReport {
  magnet_type: 'execution' | 'cost' | 'confidence' | 'validation' | 'security' | 'memory';
  observations: Record<string, any>;
  anomalies: Anomaly[];
  score: number; // 0-1, higher = more confident
  timestamp: number;
}

/**
 * Something unexpected detected by a magnet
 */
export interface Anomaly {
  level: 'info' | 'warn' | 'error';
  message: string;
  evidence: Record<string, any>;
  suggested_action?: string;
}

/**
 * Core RuntimeAdapter interface
 *
 * Each runtime (roach-pi, LangGraph, etc.) wraps itself in an adapter
 * that speaks the Chromatic Harness protocol.
 */
export interface RuntimeAdapter {
  /**
   * Unique identifier for this runtime
   */
  readonly runtime_id: string;

  /**
   * Human-readable name
   */
  readonly runtime_name: string;

  /**
   * Execute a mission using this runtime
   *
   * @param packet The mission to execute
   * @returns Execution result with telemetry, learnings, and magnet reports
   * @throws If mission fails at governance gate or execution errors are unrecoverable
   */
  executeMission(packet: MissionPacket): Promise<ExecutionResult>;

  /**
   * Check if this runtime can handle the given mission type
   *
   * @param intent The user's stated goal
   * @param scope Required file paths
   * @returns true if capable
   */
  canHandle(intent: string, scope: string[]): Promise<boolean>;

  /**
   * Validate that a mission packet is well-formed for this runtime
   *
   * @param packet Mission packet to validate
   * @returns Validation result with errors if invalid
   */
  validate(packet: MissionPacket): Promise<ValidationResult>;

  /**
   * Get runtime-specific capabilities and limitations
   * Used by CMP to decide if routing is appropriate
   */
  capabilities(): RuntimeCapabilities;

  /**
   * Clean up any resources (stop services, close connections, etc.)
   */
  shutdown(): Promise<void>;
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * Runtime capabilities declaration
 */
export interface RuntimeCapabilities {
  supported_frameworks: string[];
  max_token_budget: number;
  max_tool_calls: number;
  supported_tool_categories: string[];
  can_parallelize: boolean;
  can_recover_from_errors: boolean;
  can_test_output: boolean;
  sandbox_max_level: number; // L0-5; 5 = fully trusted
}
