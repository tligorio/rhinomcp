using System;
using System.Linq;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    private RhinoObject getObjectByIdOrName(JObject parameters)
    {
        string objectId = parameters["id"]?.ToString();
        string objectName = parameters["name"]?.ToString();

        var doc = RhinoDoc.ActiveDoc;
        RhinoObject obj = null;

        if (!string.IsNullOrEmpty(objectId))
            obj = doc.Objects.Find(new Guid(objectId));
        else if (!string.IsNullOrEmpty(objectName))
        {
            // we assume there's only one of the object with the given name
            var objs = doc.Objects.GetObjectList(new ObjectEnumeratorSettings() { NameFilter = objectName }).ToList();
            if (objs == null) throw new InvalidOperationException($"Object with name {objectName} not found.");
            if (objs.Count > 1) throw new InvalidOperationException($"Multiple objects with name {objectName} found.");
            obj = objs[0];
        }

        if (obj == null)
            throw new InvalidOperationException($"Object with ID {objectId} not found");
        return obj;
    }

    private Transform applyRotation(JObject parameters, GeometryBase geometry){
        double[] rotation = parameters["rotation"].ToObject<double[]>();
        var xform = Transform.Identity;

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

        return xform;
    }
    
    private Transform applyTranslation(JObject parameters, GeometryBase geometry)
    {
        double[] translation = parameters["translation"].ToObject<double[]>();
        var xform = Transform.Identity;

        // Calculate the move transformation
        BoundingBox bbox = geometry.GetBoundingBox(true);
        Point3d center = bbox.Center;
        Point3d target = new Point3d(translation[0], translation[1], translation[2]);
        Vector3d moveVector = target - center;

        // Apply the transformation
        xform *= Transform.Translation(moveVector);
        
        return xform;
    }
    
    private Transform applyScale(JObject parameters, GeometryBase geometry)
    {
        double[] scale = parameters["scale"].ToObject<double[]>();
        var xform = Transform.Identity;

        // Calculate the center for scaling
        BoundingBox bbox = geometry.GetBoundingBox(true);
        Point3d center = bbox.Center;
        Plane plane = Plane.WorldXY;
        plane.Origin = center;

        // Create scale transformation
        Transform scaleTransform = Transform.Scale(plane, scale[0], scale[1], scale[2]);
        xform *= scaleTransform;
        
        return xform;
    }
}