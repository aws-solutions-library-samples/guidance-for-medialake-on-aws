export interface PatternExample {
  name: string;
  description: string;
  pattern: Record<string, any>;
}

export interface PatternCategory {
  category: string;
  examples: PatternExample[];
}

export const EVENTBRIDGE_PATTERN_EXAMPLES: PatternCategory[] = [
  {
    category: "AWS Services",
    examples: [
      {
        name: "S3 Object Created",
        description: "Trigger when objects are created in an S3 bucket",
        pattern: {
          source: ["aws.s3"],
          "detail-type": ["Object Created"],
          detail: {
            bucket: {
              name: ["my-bucket"],
            },
          },
        },
      },
      {
        name: "EC2 State Change",
        description: "Trigger when EC2 instances change state",
        pattern: {
          source: ["aws.ec2"],
          "detail-type": ["EC2 Instance State-change Notification"],
          detail: {
            state: ["running", "stopped"],
          },
        },
      },
      {
        name: "Lambda Function Invocation",
        description: "Trigger on Lambda function invocations",
        pattern: {
          source: ["aws.lambda"],
          "detail-type": ["AWS API Call via CloudTrail"],
          detail: {
            eventName: ["Invoke"],
          },
        },
      },
    ],
  },
  {
    category: "String Matching",
    examples: [
      {
        name: "File Type Filter (Suffix)",
        description: "Match files with .png extension",
        pattern: {
          detail: {
            FileName: [{ suffix: ".png" }],
          },
        },
      },
      {
        name: "Region Filter (Prefix)",
        description: "Match events from US regions only",
        pattern: {
          detail: {
            Region: [{ prefix: "us-" }],
          },
        },
      },
      {
        name: "Path Filter (Wildcard)",
        description: "Match files in uploads/media directory",
        pattern: {
          detail: {
            FilePath: [{ wildcard: "/uploads/*/media/*" }],
          },
        },
      },
      {
        name: "Case Insensitive Match",
        description: "Match status regardless of case",
        pattern: {
          detail: {
            Status: [{ "equals-ignore-case": "completed" }],
          },
        },
      },
    ],
  },
  {
    category: "Numeric Matching",
    examples: [
      {
        name: "Price Range",
        description: "Match prices between $10 and $100",
        pattern: {
          detail: {
            Price: [{ numeric: [">", 10, "<=", 100] }],
          },
        },
      },
      {
        name: "File Size Limit",
        description: "Match files smaller than 10MB",
        pattern: {
          detail: {
            FileSizeBytes: [{ numeric: ["<", 10485760] }],
          },
        },
      },
      {
        name: "Exact Count",
        description: "Match exact count of 5",
        pattern: {
          detail: {
            Count: [{ numeric: ["=", 5] }],
          },
        },
      },
    ],
  },
  {
    category: "Negation (anything-but)",
    examples: [
      {
        name: "Exclude State",
        description: "Match any state except initializing",
        pattern: {
          detail: {
            state: [{ "anything-but": "initializing" }],
          },
        },
      },
      {
        name: "Exclude Multiple States",
        description: "Match any state except stopped or overloaded",
        pattern: {
          detail: {
            state: [{ "anything-but": ["stopped", "overloaded"] }],
          },
        },
      },
      {
        name: "Exclude File Types",
        description: "Match files except .tmp files",
        pattern: {
          detail: {
            FileName: [{ "anything-but": { suffix: ".tmp" } }],
          },
        },
      },
      {
        name: "Exclude Regions",
        description: "Match events not from US regions",
        pattern: {
          detail: {
            Region: [{ "anything-but": { prefix: "us-" } }],
          },
        },
      },
      {
        name: "Exclude Path Pattern",
        description: "Match files not in /lib/ directory",
        pattern: {
          detail: {
            FilePath: [{ "anything-but": { wildcard: "*/lib/*" } }],
          },
        },
      },
    ],
  },
  {
    category: "Existence & Special",
    examples: [
      {
        name: "Field Exists",
        description: "Match when ProductName field exists",
        pattern: {
          detail: {
            ProductName: [{ exists: true }],
          },
        },
      },
      {
        name: "Field Does Not Exist",
        description: "Match when ProductName field is missing",
        pattern: {
          detail: {
            ProductName: [{ exists: false }],
          },
        },
      },
      {
        name: "Null Value",
        description: "Match when UserID is null",
        pattern: {
          detail: {
            UserID: [null],
          },
        },
      },
      {
        name: "Empty String",
        description: "Match when LastName is empty",
        pattern: {
          detail: {
            LastName: [""],
          },
        },
      },
    ],
  },
  {
    category: "Complex Patterns",
    examples: [
      {
        name: "Multiple Conditions ($or)",
        description: "Match if Location is New York OR Day is Monday",
        pattern: {
          detail: {
            $or: [{ Location: ["New York"] }, { Day: ["Monday"] }],
          },
        },
      },
      {
        name: "Complex $or with Numeric",
        description: "Match multiple conditions with numeric ranges",
        pattern: {
          detail: {
            $or: [
              { "c-count": [{ numeric: [">", 0, "<=", 5] }] },
              { "d-count": [{ numeric: ["<", 10] }] },
              { "x-limit": [{ numeric: ["=", 3.018e2] }] },
            ],
          },
        },
      },
      {
        name: "IP Address Range",
        description: "Match IP addresses in 10.0.0.0/24 subnet",
        pattern: {
          detail: {
            sourceIPAddress: [{ cidr: "10.0.0.0/24" }],
          },
        },
      },
      {
        name: "Multiple Fields Combined",
        description: "Match specific source and detail-type",
        pattern: {
          source: ["aws.s3"],
          "detail-type": ["Object Created"],
          detail: {
            bucket: {
              name: [{ prefix: "media-" }],
            },
            object: {
              key: [{ suffix: ".mp4" }],
            },
          },
        },
      },
    ],
  },
  {
    category: "Media & Asset Processing",
    examples: [
      {
        name: "Video File Upload",
        description: "Trigger on video file uploads",
        pattern: {
          source: ["aws.s3"],
          "detail-type": ["Object Created"],
          detail: {
            object: {
              key: [{ suffix: ".mp4" }, { suffix: ".mov" }, { suffix: ".avi" }],
            },
          },
        },
      },
      {
        name: "Image File Upload",
        description: "Trigger on image file uploads",
        pattern: {
          source: ["aws.s3"],
          "detail-type": ["Object Created"],
          detail: {
            object: {
              key: [{ suffix: ".jpg" }, { suffix: ".jpeg" }, { suffix: ".png" }],
            },
          },
        },
      },
      {
        name: "Audio File Upload",
        description: "Trigger on audio file uploads",
        pattern: {
          source: ["aws.s3"],
          "detail-type": ["Object Created"],
          detail: {
            object: {
              key: [{ suffix: ".mp3" }, { suffix: ".wav" }, { suffix: ".aac" }],
            },
          },
        },
      },
      {
        name: "Large File Upload",
        description: "Trigger on files larger than 100MB",
        pattern: {
          source: ["aws.s3"],
          "detail-type": ["Object Created"],
          detail: {
            object: {
              size: [{ numeric: [">", 104857600] }],
            },
          },
        },
      },
    ],
  },
];
