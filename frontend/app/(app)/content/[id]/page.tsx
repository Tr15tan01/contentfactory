import { PostEditor } from "@/components/app/content/post-editor";

export const metadata = { title: "Post" };

export default async function ContentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  return <PostEditor id={(await params).id} />;
}
