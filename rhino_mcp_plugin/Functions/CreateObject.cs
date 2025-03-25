using System;
using System.Collections.Generic;
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
            string type = castToString(parameters.SelectToken("type"));
            string name = castToString(parameters.SelectToken("name"));
            bool customColor = parameters.ContainsKey("color");
            int[] color = castToIntArray(parameters.SelectToken("color"));
            JObject geoParams = (JObject)parameters.SelectToken("params");
            
            var doc = RhinoDoc.ActiveDoc;
            Guid objectId = Guid.Empty;

            // Create a box centered at the specified point
            switch (type)
            {
                case "POINT":
                    objectId = doc.Objects.AddPoint(0,0,0);
                    break;
                case "LINE":
                    double[] start = castToDoubleArray(geoParams.SelectToken("start"));
                    double[] end = castToDoubleArray(geoParams.SelectToken("end"));
                    var ptStart = new Point3d(start[0], start[1], start[2]);
                    var ptEnd = new Point3d(end[0], end[1], end[2]);
                    objectId = doc.Objects.AddLine(ptStart, ptEnd);
                    break;
                case "POLYLINE":
                    List<Point3d> ptList = castToPoint3dList(geoParams.SelectToken("points"));
                    objectId = doc.Objects.AddPolyline(ptList);
                    break;
                case "CURVE":
                    List<Point3d> controlPoints = castToPoint3dList(geoParams.SelectToken("points"));
                    int degree = castToInt(geoParams.SelectToken("degree"));
                    var curve = Curve.CreateControlPointCurve(controlPoints, degree);
                    if (curve == null)
                    {
                        throw new InvalidOperationException("unable to create control point curve from given points");
                    }
                    objectId = doc.Objects.AddCurve(curve);
                    break;
                case "BOX":
                    // parse size
                    double width = castToDouble(geoParams.SelectToken("width"));
                    double length = castToDouble(geoParams.SelectToken("length"));
                    double height = castToDouble(geoParams.SelectToken("height"));
                    double xSize = width, ySize = length, zSize = height;
                    Box box = new Box(
                        Plane.WorldXY,
                        new Interval(-xSize / 2, xSize / 2),
                        new Interval(-ySize / 2, ySize / 2),
                        new Interval(-zSize / 2, zSize / 2)
                    );
                    objectId = doc.Objects.AddBox(box);
                    break;
                    
                case "SPHERE":
                    // parse radius
                    double radius = castToDouble(geoParams.SelectToken("radius"));
                    // Create sphere at origin with specified radius
                    Sphere sphere = new Sphere(Point3d.Origin, radius);
                    // Convert sphere to BREP for adding to document
                    objectId = doc.Objects.AddBrep(sphere.ToBrep());
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