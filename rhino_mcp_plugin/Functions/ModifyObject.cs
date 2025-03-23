using System;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.Geometry;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject ModifyObject(JObject parameters)
        {
            var doc = RhinoDoc.ActiveDoc;
            var obj = getObjectByIdOrName(parameters);
            var geometry = obj.Geometry;
            var xform = Transform.Identity;

            // Handle different modifications based on parameters
            bool attributesModified = false;
            bool geometryModified = false;

            // Change name if provided
            if (parameters["new_name"] != null)
            {
                string name = parameters["new_name"].ToString();
                obj.Attributes.Name = name;
                attributesModified = true;
            }

            // Change location if provided
            if (parameters["location"] != null && obj.Geometry != null)
            {
                double[] location = parameters["location"].ToObject<double[]>();

                // Calculate the move transformation
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;
                Point3d target = new Point3d(location[0], location[1], location[2]);
                Vector3d moveVector = target - center;

                // Apply the transformation
                xform *= Transform.Translation(moveVector);
                geometryModified = true;
            }

            // Apply scale if provided
            if (parameters["scale"] != null && obj.Geometry != null)
            {
                double[] scale = parameters["scale"].ToObject<double[]>();

                // Calculate the center for scaling
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;
                Plane plane = Plane.WorldXY;
                plane.Origin = center;

                // Create scale transformation
                Transform scaleTransform = Transform.Scale(plane, scale[0], scale[1], scale[2]);
                xform *= scaleTransform;
                geometryModified = true;
            }

            // Apply rotation if provided
            if (parameters["rotation"] != null && obj.Geometry != null)
            {
                double[] rotation = parameters["rotation"].ToObject<double[]>();

                // Calculate the center for rotation
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;

                // Create rotation transformations (in radians)
                Transform rotX = Transform.Rotation(rotation[0], Vector3d.XAxis, center);
                Transform rotY = Transform.Rotation(rotation[1], Vector3d.YAxis, center);
                Transform rotZ = Transform.Rotation(rotation[2], Vector3d.ZAxis, center);

                // Apply transformations
                xform *= rotX;
                xform *= rotY;
                xform *= rotZ;

                // Update the object
                geometryModified = true;
            }

            if (attributesModified)
            {
                // Update the object attributes if needed
                doc.Objects.ModifyAttributes(obj, obj.Attributes, true);
            }

            if (geometryModified)
            {
                // Update the object geometry if needed
                doc.Objects.Transform(obj, xform, true);
            }

            // Update views
            doc.Views.Redraw();

            return GetObjectInfo(new JObject { ["id"] = obj.Id });
        }
}