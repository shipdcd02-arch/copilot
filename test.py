<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net47</TargetFramework>
    <UseWPF>true</UseWPF>
    <AssemblyName>InterferenceCheck</AssemblyName>
    <RootNamespace>InterferenceCheck</RootNamespace>
    <PlatformTarget>x64</PlatformTarget>
    <LangVersion>8.0</LangVersion>
    <Nullable>disable</Nullable>
    <AcadDir>C:\Program Files\Autodesk\AutoCAD 2018</AcadDir>
  </PropertyGroup>

  <ItemGroup>
    <Reference Include="AcCoreMgd">
      <HintPath>$(AcadDir)\AcCoreMgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="AcDbMgd">
      <HintPath>$(AcadDir)\AcDbMgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Reference Include="AcMgd">
      <HintPath>$(AcadDir)\AcMgd.dll</HintPath>
      <Private>False</Private>
    </Reference>
  </ItemGroup>
</Project>