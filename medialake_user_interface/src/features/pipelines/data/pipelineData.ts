import { CreatePipelineRequest } from "@/api/types/pipeline.types";

export const hardcodedPipelineData: CreatePipelineRequest = {
  name: "image-pipeline",
  type: "Event Triggered",
  system: true,
  definition: {
    nodes: [
      {
        id: "dndnode_0",
        type: "custom",
        position: {
          x: 154,
          y: 273,
        },
        data: {
          id: "03c23094-d405-4aa7-a243-5a7a8f71d4a5",
          type: "imageasset",
          label: "Image Asset",
          icon: {
            key: null,
            ref: null,
            props: {
              size: 20,
            },
            _owner: null,
          },
          inputTypes: ["image"],
          outputTypes: ["image"],
        },
        width: 60,
        height: 55,
        positionAbsolute: {
          x: 154,
          y: 273,
        },
      },
      {
        id: "dndnode_2",
        type: "custom",
        position: {
          x: 187,
          y: 380,
        },
        data: {
          id: "57207390-4b93-4c07-a1cc-e4733710b842",
          type: "imagemetadata",
          label: "Image Metadata",
          icon: {
            key: null,
            ref: null,
            props: {
              size: 20,
            },
            _owner: null,
          },
          inputTypes: ["image"],
          outputTypes: ["image"],
        },
        width: 60,
        height: 55,
        positionAbsolute: {
          x: 187,
          y: 380,
        },
      },
      {
        id: "dndnode_3",
        type: "custom",
        position: {
          x: 196,
          y: 467,
        },
        data: {
          id: "9361ac53-13e9-4358-adde-3e4cd023954f",
          type: "imageproxy",
          label: "Image Proxy",
          icon: {
            key: null,
            ref: null,
            props: {
              size: 20,
            },
            _owner: null,
          },
          inputTypes: ["image"],
          outputTypes: ["image"],
        },
        width: 60,
        height: 55,
        selected: true,
        positionAbsolute: {
          x: 196,
          y: 467,
        },
        dragging: false,
      },
      {
        id: "dndnode_4",
        type: "custom",
        position: {
          x: 216,
          y: 582,
        },
        data: {
          id: "6773f9ef-2161-42c1-9485-11ef1c23f3b4",
          type: "imagethumbnail",
          label: "Image Thumbnail",
          icon: {
            key: null,
            ref: null,
            props: {
              size: 20,
            },
            _owner: null,
          },
          inputTypes: ["image"],
          outputTypes: ["image"],
        },
        width: 60,
        height: 55,
        positionAbsolute: {
          x: 216,
          y: 582,
        },
      },
      {
        id: "dndnode_5",
        type: "custom",
        position: {
          x: 317.4421648673655,
          y: 644.8991829079268,
        },
        data: {
          id: "14a670a0-967d-452c-9e0e-cf2f9e92d634",
          type: "medialake",
          label: "MediaLake",
          icon: {
            key: null,
            ref: null,
            props: {
              size: 20,
            },
            _owner: null,
          },
          inputTypes: ["video", "audio", "image", "metadata"],
          outputTypes: [],
        },
        width: 60,
        height: 55,
        positionAbsolute: {
          x: 317.4421648673655,
          y: 644.8991829079268,
        },
      },
    ],
    edges: [
      {
        source: "dndnode_0",
        sourceHandle: null,
        target: "dndnode_2",
        targetHandle: null,
        type: "custom",
        data: {
          text: "to Image Metadata",
        },
        id: "reactflow__edge-dndnode_0-dndnode_2",
      },
      {
        source: "dndnode_2",
        sourceHandle: null,
        target: "dndnode_3",
        targetHandle: null,
        type: "custom",
        data: {
          text: "to Image Proxy",
        },
        id: "reactflow__edge-dndnode_2-dndnode_3",
      },
      {
        source: "dndnode_3",
        sourceHandle: null,
        target: "dndnode_4",
        targetHandle: null,
        type: "custom",
        data: {
          text: "to Image Thumbnail",
        },
        id: "reactflow__edge-dndnode_3-dndnode_4",
      },
      {
        source: "dndnode_4",
        sourceHandle: null,
        target: "dndnode_5",
        targetHandle: null,
        type: "custom",
        data: {
          text: "to MediaLake",
        },
        id: "reactflow__edge-dndnode_4-dndnode_5",
      },
    ],
    viewport: {
      x: -130.31858746589876,
      y: -141.11180335713357,
      zoom: 0.9460576467255969,
    },
  },
};
