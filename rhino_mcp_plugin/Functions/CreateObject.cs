using System;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.Geometry;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject CreateObject(JObject parameters)
        {
            string type = parameters["type"]?.ToString() ?? "CUBE";
            string name = parameters["name"]?.ToString();

            // Parse location, rotation, scale
            double[] location = parameters["location"]?.ToObject<double[]>() ?? new double[] { 0, 0, 0 };
            double[] rotation = parameters["rotation"]?.ToObject<double[]>() ?? new double[] { 0, 0, 0 };
            double[] scale = parameters["scale"]?.ToObject<double[]>() ?? new double[] { 1, 1, 1 };

            Point3d point = new Point3d(location[0], location[1], location[2]);

            var doc = RhinoDoc.ActiveDoc;
            Guid objectId = Guid.Empty;

            switch (type.ToUpper())
            {
                case "CUBE":
                case "BOX":
                    // Create a box centered at the specified point
                    double xSize = scale[0], ySize = scale[1], zSize = scale[2];
                    Box box = new Box(
                        new Plane(point, Vector3d.XAxis, Vector3d.YAxis),
                        new Interval(-xSize / 2, xSize / 2),
                        new Interval(-ySize / 2, ySize / 2),
                        new Interval(-zSize / 2, zSize / 2)
                    );
                    objectId = doc.Objects.AddBox(box);
                    break;

                case "SPHERE":
                    // Create a sphere at the specified point
                    double radius = scale[0]; // Use X scale as radius
                    Sphere sphere = new Sphere(point, radius);
                    objectId = doc.Objects.AddSphere(sphere);
                    break;

                case "PLANE":
                    // Create a plane at the specified point
                    double width = scale[0];
                    double length = scale[1];
                    Plane plane = new Plane(point, Vector3d.ZAxis);
                    Rectangle3d rectangle = new Rectangle3d(
                        plane,
                        new Interval(-width / 2, width / 2),
                        new Interval(-length / 2, length / 2)
                    );
                    objectId = doc.Objects.AddRectangle(rectangle);
                    break;

                case "POINT":
                    // Create a point at the specified location
                    objectId = doc.Objects.AddPoint(point);
                    break;

                default:
                    throw new ArgumentException($"Unsupported object type: {type}");
            }

            if (objectId == Guid.Empty)
                throw new InvalidOperationException("Failed to create object");

            // Set name if provided
            if (!string.IsNullOrEmpty(name))
            {
                var rhinoObject = doc.Objects.Find(objectId);
                if (rhinoObject != null)
                {
                    rhinoObject.Attributes.Name = name;
                    doc.Objects.ModifyAttributes(rhinoObject, rhinoObject.Attributes, true);
                }
            }

            // Update views
            doc.Views.Redraw();

            // Return information about the created object
            var result = new JObject
            {
                ["id"] = objectId.ToString(),
                ["name"] = name ?? "",
                ["type"] = type,
                ["location"] = new JArray { location[0], location[1], location[2] },
                ["rotation"] = new JArray { rotation[0], rotation[1], rotation[2] },
                ["scale"] = new JArray { scale[0], scale[1], scale[2] }
            };

            // Add bounding box info
            var obj = doc.Objects.Find(objectId);
            if (obj != null && obj.Geometry != null)
            {
                BoundingBox bbox = obj.Geometry.GetBoundingBox(true);
                result["world_bounding_box"] = new JArray
                {
                    new JArray { bbox.Min.X, bbox.Min.Y, bbox.Min.Z },
                    new JArray { bbox.Max.X, bbox.Max.Y, bbox.Max.Z }
                };
            }

            return result;
        }
}