using System;
using System.Drawing;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject CreateObject(JObject parameters)
        {
            // parse meta data
            string type = parameters["type"]?.ToString();
            string name = parameters["name"]?.ToString();
            bool customColor = parameters.ContainsKey("color");
            int[] color = parameters["color"]?.ToObject<int[]>() ?? new [] { 0, 0, 0 };
            
            var doc = RhinoDoc.ActiveDoc;
            Guid objectId = Guid.Empty;

            // Create a box centered at the specified point
            switch (type)
            {
                case "BOX":
                    // parse size
                    double width = parameters.SelectToken("params.width")?.ToObject<double>() ?? 1;
                    double length = parameters.SelectToken("params.length")?.ToObject<double>() ?? 1;
                    double height = parameters.SelectToken("params.height")?.ToObject<double>() ?? 1;
                    double xSize = width, ySize = length, zSize = height;
                    Box box = new Box(
                        Plane.WorldXY,
                        new Interval(-xSize / 2, xSize / 2),
                        new Interval(-ySize / 2, ySize / 2),
                        new Interval(-zSize / 2, zSize / 2)
                    );
                    objectId = doc.Objects.AddBox(box);
                    break;
            }
            
            if (objectId == Guid.Empty)
                throw new InvalidOperationException("Failed to create object");
            
            var rhinoObject = doc.Objects.Find(objectId);
            if (rhinoObject != null)
            {
                if (!string.IsNullOrEmpty(name)) rhinoObject.Attributes.Name = name;
                if (customColor)
                {
                    rhinoObject.Attributes.ColorSource = ObjectColorSource.ColorFromObject;
                    rhinoObject.Attributes.ObjectColor = Color.FromArgb(color[0], color[1], color[2]);
                }
                doc.Objects.ModifyAttributes(rhinoObject, rhinoObject.Attributes, true);
            }
            
            // Update views
            doc.Views.Redraw();

            // apply modification
            parameters["id"] = objectId;
            return ModifyObject(parameters);
        }
}