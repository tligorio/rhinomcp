using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;

namespace rhinomcp.Serializers
{
    public static class Serializer
    {
        public static RhinoDoc doc = RhinoDoc.ActiveDoc;

        public static JObject Color(Color color)
        {
            return new JObject()
            {
                ["r"] = color.R,
                ["g"] = color.G,
                ["b"] = color.B
            };
        }

        public static JArray Point(Point3d pt)
        {
            return new JArray
            {
                Math.Round(pt.X, 2),
                Math.Round(pt.Y, 2),
                Math.Round(pt.Z, 2)
            };
        }

        public static JArray BBox(BoundingBox bbox)
        {
            return new JArray
            {
                new JArray { bbox.Min.X, bbox.Min.Y, bbox.Min.Z },
                new JArray { bbox.Max.X, bbox.Max.Y, bbox.Max.Z }
            };
        }

        public static JObject RhinoObject(RhinoObject obj)
        {
            var objInfo = new JObject
            {
                ["id"] = obj.Id.ToString(),
                ["name"] = obj.Name ?? "(unnamed)",
                ["type"] = obj.ObjectType.ToString(),
                ["layer"] = doc.Layers[obj.Attributes.LayerIndex].Name,
                ["material"] = obj.Attributes.MaterialIndex.ToString(),
                ["color"] = Color(obj.Attributes.ObjectColor)
            };

            // Add location data if applicable
            if (obj.Geometry is GeometryBase geometry)
            {
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;

                objInfo["location"] = Point(center);
                objInfo["bounding_box"] = BBox(bbox);
            }

            return objInfo;
        }
    }
}
